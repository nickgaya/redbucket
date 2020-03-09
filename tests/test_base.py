from unittest.mock import NonCallableMock

import pytest
from redis import Redis

from redbucket.base import RateLimiter, RedisRateLimiter
from redbucket.data import RateLimit, Zone


class DummyRateLimiter(RateLimiter):
    """Dummy rate limiter used to test abstract base class functionality."""

    def _request(self, keys):
        for lname in keys:
            self._rate_limits[lname]
        return False, None


def test_conflicting_rate_limits():
    z1 = Zone('z1', 1)
    z2 = Zone('z2', 2)
    l1 = RateLimit(z1)
    l2 = RateLimit(z2, burst=3)
    l3 = RateLimit(z1, delay=1)

    rl = DummyRateLimiter()
    with pytest.raises(ValueError) as ei:
        rl.configure(k1=l1, k2=l2, k3=l3)

    assert str(ei.value) == "Multiple rate limits for zone 'z1'"


def test_reconfigure():
    rl = DummyRateLimiter()
    rl.configure(k1=RateLimit(Zone('z1', 1)))

    with pytest.raises(RuntimeError) as ei:
        rl.configure(k2=RateLimit(Zone('z2', 2)))

    assert str(ei.value) == "Rate limiter already configured"


def test_not_configured():
    rl = DummyRateLimiter()

    with pytest.raises(RuntimeError) as ei:
        rl.request(k1='foo')

    assert str(ei.value) == "Rate limiter not configured"


def test_expiry_warning():
    z1 = Zone('z1', 2, 5)
    l1 = RateLimit(z1, burst=4, delay=6)
    rl = DummyRateLimiter()

    with pytest.warns(UserWarning) as rec:
        rl.configure(k1=l1)

    assert len(rec) == 1
    assert str(rec[0].message) == ("Expiry for zone 'z1' is less than "
                                   "recommended minimum for limit 'k1': "
                                   "expiry=5, recommended=6")


class DummyRedisRateLimiter(RedisRateLimiter):

    MIN_REDIS_VERSION = (1, 2)

    def _request(self, **keys):
        for lname in keys:
            self._rate_limits[lname]
        return False, None


@pytest.fixture
def mock_redis():
    mock_redis = NonCallableMock(name='redis', spec=Redis)
    mock_redis.info.return_value = {'redis_version': '2.6.17'}
    return mock_redis


@pytest.mark.parametrize('format_string', (
    'invalid {',
    'no fields',
    '{zone} no key',
    'no zone {key}',
    '{zone} {key} extra {}',
    '{zone} {key} {extra}',
    '{zone} {key} extra {0}',
))
def test_invalid_key_format(mock_redis, format_string):
    with pytest.raises(ValueError):
        DummyRedisRateLimiter(mock_redis, key_format=format_string)


@pytest.mark.parametrize('format_string', (
    '{zone}{key}',
    '{key}{zone}',
    '{zone}{key}{zone}',
    '{zone!r}{key}',
    '{{{zone}{key}}}',
))
def test_valid_key_format(mock_redis, format_string):
    DummyRedisRateLimiter(mock_redis, key_format=format_string)


def test_version_check(mock_redis):
    mock_redis.info.return_value = {'redis_version': '1.0.1'}

    with pytest.raises(RuntimeError) as e:
        DummyRedisRateLimiter(mock_redis)

    assert str(e.value) == "Redis server has version 1.0.1. This " \
        "implementation requires version 1.2 or greater."

    mock_redis.info.assert_called_once_with('server')
