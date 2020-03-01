"""Generic class definitions used across rate limiter implementations."""

import collections
import math
import sys
import warnings
from abc import ABC, abstractmethod

if sys.version_info >= (3, 7):
    namedtuple = collections.namedtuple
else:
    def namedtuple(typename, field_names, *, defaults=None):
        """Create a namedtuple with default field values."""
        cls = collections.namedtuple(typename, field_names)
        cls.__new__.__defaults__ = defaults
        return cls

Zone = namedtuple('Zone', ('name', 'rate', 'expiry'), defaults=(60,))
Zone.__doc__ += ': Namespace for rate limiting state'
Zone.name.__doc__ = 'Unique identifier for this zone'
Zone.rate.__doc__ = 'Rate limit in requests per second'
Zone.expiry.__doc__ = 'Zone expiry in seconds'

RateLimit = namedtuple('RateLimit', ('zone', 'burst', 'delay'),
                       defaults=(0, 0))
RateLimit.__doc__ += ': Rate limit for a given zone'
RateLimit.zone.__doc__ = 'Rate limiting zone'
RateLimit.burst.__doc__ = 'Maximum burst with no delay'
RateLimit.delay.__doc__ = 'Maximum burst with delay'

State = namedtuple('State', ('timestamp', 'value'))
State.__doc__ += ': Internal rate limiting state'
State.timestamp.__doc__ = 'Unix timestamp of last update'
State.value.__doc__ = 'Time-adjusted request count'


class RateLimiter(ABC):
    """Abstract base class for rate limiter implementations."""

    def __init__(self):
        """Initialize a RateLimiter instance."""
        self._configured = False

    def configure(self, **rate_limits):
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

    def _validate(self, rate_limits):
        zones = set()
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

    def _configure(self, rate_limits):
        pass

    def request(self, **keys):
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
    def _request(self, keys):
        ...
