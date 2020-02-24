"""In-memory rate limiter implementation."""

import contextlib
import threading
import time
from collections import namedtuple

from redbucket.base import RateLimiter

ZoneState = namedtuple('ZoneState', ('state', 'lock'))
Req = namedtuple('Req', ('limit', 'zstate', 'key'))


class InMemoryRateLimiter(RateLimiter):
    """
    Thread-safe in-memory rate limiter.

    This implementation is primarily intended to demonstrate the
    characteristics of the rate limiting algorithm. The rate limiter stores
    zone state for all keys indefinitely, making it unsuitable for long-term
    production use.
    """

    def _configure(self, rate_limits):
        self._zones = {
            limit.zone.name: ZoneState({}, threading.Lock())
            for limit in rate_limits.values()
        }

    def _request(self, keys):
        reqs = []
        for lname, key in keys.items():
            limit = self._rate_limits[lname]
            zstate = self._zones[limit.zone.name]
            reqs.append(Req(limit, zstate, key))
        # Sort by zone to avoid deadlocks
        reqs.sort(key=lambda req: id(req.zstate))

        with contextlib.ExitStack() as stack:
            for req in reqs:
                stack.enter_context(req.zstate.lock)

            t1 = time.monotonic()
            delay = 0
            states = []
            for limit, (state, _), key in reqs:
                t0, v0 = state.get(key) or (t1, 0)
                v1 = max(v0 - (t1 - t0) * limit.zone.rate, 0) + 1
                c = limit.burst + 1 - v1
                if c < -limit.delay:
                    return False, None
                if c < 0:
                    delay = max(delay, -c/limit.zone.rate)
                states.append((t1, v1))

            for req, state in zip(reqs, states):
                req.zstate.state[req.key] = state

        return True, delay
