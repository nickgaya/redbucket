"""Rate limiter base classes."""

import math
import warnings
from abc import ABC, abstractmethod
from string import Formatter
from typing import Any, Mapping, Set, Tuple

from redis import Redis, ResponseError
from redbucket.data import RateLimit, Response

__all__ = ('RateLimiter', 'RedisRateLimiter', 'get_redis_version')


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


class RedisRateLimiter(RateLimiter):
    """Base class for Redis-based rate limiters."""

    MIN_REDIS_VERSION: Tuple[int, ...] = ()

    def __init__(self, redis: Redis,
                 key_format: str = 'redbucket:{zone}:{key}') -> None:
        """
        Initialize a RedisRateLimiter instance.

        :param redis: Redis client
        :param key_format: Redis key format. Must contain replacement fields
            'zone' and 'key'.
        """
        super(RedisRateLimiter, self).__init__()
        self._redis = redis
        self._key_format = _validate_key_format(key_format)

        if self.MIN_REDIS_VERSION:
            self._check_redis_version()

    def _redis_key(self, zone: Any, key: Any) -> str:
        return self._key_format.format(zone=zone, key=key)

    def _redis_version(self):
        return get_redis_version(self._redis)

    def _check_redis_version(self):
        version = self._redis_version()
        if version < self.MIN_REDIS_VERSION:
            server_version = '.'.join(map(str, version))
            min_version = '.'.join(map(str, self.MIN_REDIS_VERSION))
            raise RuntimeError(
                f"Redis server has version {server_version}. This "
                f"implementation requires version {min_version} or greater.")


def get_redis_version(redis: Redis) -> Tuple[int, ...]:
    """Query the Redis server version as a tuple of ints."""
    try:
        info = redis.info('server')
    except ResponseError:
        info = redis.info()
    return tuple(map(int, info['redis_version'].split('.')))


def _validate_key_format(format_string: str) -> str:
    """Make sure that the given key format string has the correct fields."""
    field_names = {ft[1] for ft in Formatter().parse(format_string)}
    field_names.discard(None)
    expected = {'zone', 'key'}
    if any(name not in field_names for name in expected):
        raise ValueError("Key format string must contain replacement fields "
                         "'zone' and 'key'")
    if field_names != expected:
        raise ValueError("Key format string can only contain replacement "
                         "'zone' and 'key'")
    return format_string
