"""In-memory rate limiter implementation."""

import contextlib
import threading
import time
from collections import namedtuple

_RateLimit = namedtuple('_RateLimit', ('limit', 'state', 'lock'))
_Req = namedtuple('_Req', ('rl', 'key'))


class InMemoryRateLimiter:
    """
    Thread-safe in-memory rate limiter.

    This implementation is primarily intended to demonstrate the
    characteristics of the rate limiting algorithm. The rate limiter stores
    zone state for all keys indefinitely, making it unsuitable for long-term
    production use.
    """

    def __init__(self, **rate_limits):
        """
        Initialize an InMemoryRateLimiter instance.

        :param **rate_limits: Map of identifiers to rate limits.
        """
        zones = set()
        for limit in rate_limits.values():
            zname = limit.zone.name
            if zname in zones:
                raise ValueError(f"Multiple rate limits for zone {zname!r}")
            zones.add(zname)

        self.rate_limits = {
            lname: _RateLimit(limit, {}, threading.Lock())
            for lname, limit in rate_limits.items()
        }

    def request(self, **keys):
        """
        Request a permit from the rate limiter.

        :param **keys: Map of rate limit identifiers to keys.
        :return: A pair (success, delay) indicating whether the request was
            accepted, and, if so, how long the request should be delayed in
            seconds. Note that it is the caller's responsibility to enforce
            this delay.
        """
        reqs = [_Req(self.rate_limits[lname], key)
                for lname, key in keys.items()]
        # Sort by rate limit to avoid deadlocks
        reqs.sort(key=lambda req: id(req.rl))

        with contextlib.ExitStack() as stack:
            for req in reqs:
                stack.enter_context(req.rl.lock)

            t1 = time.monotonic()
            delay = 0
            states = []
            for (limit, state, lock), key in reqs:
                t0, b0 = state.get(key) or (t1, 0)
                b1 = max(b0 - (t1 - t0) * limit.zone.rate, 0) + 1
                c = limit.burst + 1 - b1
                if c < -limit.delay:
                    return False, None
                if c < 0:
                    delay = max(delay, -c/limit.zone.rate)
                states.append((t1, b1))

            for req, state in zip(reqs, states):
                req.rl.state[req.key] = state

        return True, delay

    def __repr__(self):
        """Generate a string representation of this instance."""
        args = (f'{lname}={rl.limit!r}'
                for lname, rl in self.rate_limits.items())
        return f"{self.__class__.__qualname__}({', '.join(args)})"
