"""Data class definitions."""

from typing import Any, NamedTuple, Optional

__all__ = ('Zone', 'RateLimit', 'Response', 'State')


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
