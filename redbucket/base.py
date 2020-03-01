"""Generic class definitions used across rate limiter implementations."""

import math
import warnings
from abc import ABC, abstractmethod
from typing import Any, Mapping, NamedTuple, Optional, Set


class Zone(NamedTuple):
    """Namespace for rate limiting state."""

    name: Any
    rate: float
    expiry: int = 60


Zone.name.__doc__ = 'Unique identifier for this zone'
Zone.rate.__doc__ = 'Rate limit in requests per second'
Zone.expiry.__doc__ = 'Zone expiry in seconds'


class RateLimit(NamedTuple):
    """Rate limit for a given zone."""

    zone: Zone
    burst: float = 0
    delay: float = 0


RateLimit.zone.__doc__ = 'Rate limiting zone'
RateLimit.burst.__doc__ = 'Maximum burst with no delay'
RateLimit.delay.__doc__ = 'Maximum burst with delay'


class State(NamedTuple):
    """Internal rate limiting state."""

    timestamp: float
    value: float


State.timestamp.__doc__ = 'Unix timestamp of last update'
State.value.__doc__ = 'Time-adjusted request count'


class Response(NamedTuple):
    """Response to a rate limiter request."""

    accepted: bool
    delay: Optional[float]


Response.accepted.__doc__ = 'Whether the request was accepted'
Response.delay.__doc__ = 'Amount of time to delay the request'


class RateLimiter(ABC):
    """Abstract base class for rate limiter implementations."""

    def __init__(self) -> None:
        """Initialize a RateLimiter instance."""
        self._configured = False

    def configure(self, **rate_limits: RateLimit) -> None:
        """
        Configure rate limits for this rate limiter.

        :param **rate_limits: Map of identifiers to rate limits.
        """
        if self._configured:
            raise RuntimeError("Rate limiter already configured")

        self._validate(rate_limits)
        self._rate_limits = rate_limits
        self._configure(rate_limits)
        self._configured = True

    def _validate(self, rate_limits: Mapping[str, RateLimit]) -> None:
        zones: Set[str] = set()
        for lname, limit in rate_limits.items():
            if limit.zone.name in zones:
                raise ValueError("Multiple rate limits for zone "
                                 f"{limit.zone.name!r}")
            zones.add(limit.zone.name)

            if (limit.burst + limit.delay + 1
                    > limit.zone.expiry * limit.zone.rate):
                recommended = math.ceil((limit.burst + limit.delay + 1)
                                        / limit.zone.rate)
                warnings.warn(f"Expiry for zone {limit.zone.name!r} is less "
                              f"than recommended minimum for limit {lname!r}: "
                              f"expiry={limit.zone.expiry}, "
                              f"recommended={recommended}")

    def _configure(self, rate_limits: Mapping[str, RateLimit]) -> None:
        pass

    def request(self, **keys: Any) -> Response:
        """
        Request a permit from the rate limiter.

        :param **keys: Map of rate limit identifiers to keys.
        :return: A pair (success, delay) indicating whether the request was
            accepted, and, if so, how long the request should be delayed in
            seconds. Note that it is the caller's responsibility to enforce
            this delay.
        """
        if not self._configured:
            raise RuntimeError("Rate limiter not configured")

        return self._request(keys)

    @abstractmethod
    def _request(self, keys: Mapping[str, Any]) -> Response:
        ...
