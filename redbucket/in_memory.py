"""In-memory rate limiter implementation."""

import contextlib
import threading
import time
from typing import Any, Dict, List, Mapping, NamedTuple

from redbucket.base import RateLimiter
from redbucket.data import RateLimit, Response, State

__all__ = ('InMemoryRateLimiter',)


class _ZoneState(NamedTuple):
    state: Dict[Any, State]
    lock: threading.Lock


class _Req(NamedTuple):
    limit: RateLimit
    zstate: _ZoneState
    key: Any


class InMemoryRateLimiter(RateLimiter):
    """
    Thread-safe in-memory rate limiter.

    This implementation is primarily intended to demonstrate the
    characteristics of the rate limiting algorithm. The rate limiter stores
    zone state for all keys indefinitely, making it unsuitable for long-term
    production use.
    """

    def _configure(self, rate_limits: Mapping[str, RateLimit]) -> None:
        self._zones = {
            limit.zone.name: _ZoneState({}, threading.Lock())
            for limit in rate_limits.values()
        }

    def _request(self, keys: Mapping[str, Any]) -> Response:
        if not keys:
            return Response(True, 0)

        reqs: List[_Req] = []
        for lname, key in keys.items():
            limit = self._rate_limits[lname]
            zstate = self._zones[limit.zone.name]
            reqs.append(_Req(limit, zstate, key))
        # Sort by zone to avoid deadlocks
        reqs.sort(key=lambda req: id(req.zstate))

        with contextlib.ExitStack() as stack:
            for req in reqs:
                stack.enter_context(req.zstate.lock)

            t1 = time.monotonic()
            delay: float = 0
            states: List[State] = []
            for limit, (state, _), key in reqs:
                t0, v0 = state.get(key) or (t1, 0)
                v1 = max(v0 - (t1 - t0) * limit.zone.rate, 0) + 1
                c = limit.burst + 1 - v1
                if c < -limit.delay:
                    return Response(False, None)
                if c < 0:
                    delay = max(delay, -c/limit.zone.rate)
                states.append(State(t1, v1))

            for req, new_state in zip(reqs, states):
                req.zstate.state[req.key] = new_state

        return Response(True, delay)
