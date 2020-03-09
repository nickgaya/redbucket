import time

import pytest
from pytest import approx

from redbucket.data import RateLimit, Zone
from redbucket.script import RedisScriptRateLimiter
from redbucket.transactional import RedisTransactionalRateLimiter


@pytest.fixture(params=('tx-json', 'tx-struct',
                        'script-json', 'script-struct'))
def rate_limiter(redis, redis_version_check, key_format, request):
    impl, codec = request.param.split('-')
    cls = {
        'tx': RedisTransactionalRateLimiter,
        'script': RedisScriptRateLimiter,
    }[impl]
    if cls.MIN_REDIS_VERSION:
        redis_version_check(cls.MIN_REDIS_VERSION)
    return cls(redis, key_format=key_format, codec=codec)


def _redis_time(redis):
    s, us = redis.time()
    return s + us / 1000000


def test_state(redis, rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1)),
                           k2=RateLimit(Zone('z2', 1)))

    assert rate_limiter.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)

    time.sleep(0.1)
    assert rate_limiter.request(k1='bar', k2='baz') == (True, 0)
    t1 = _redis_time(redis)

    time.sleep(0.1)
    assert rate_limiter.request(k1='foo') == (False, None)
    assert rate_limiter.request(k1='bar') == (False, None)
    assert rate_limiter.request(k2='baz') == (False, None)

    assert rate_limiter._get_state('z1', 'foo') == approx((t0, 1))
    assert rate_limiter._get_state('z1', 'bar') == approx((t1, 1))
    assert rate_limiter._get_state('z2', 'baz') == approx((t1, 1))


def test_state_burst(redis, rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1), burst=1))

    assert rate_limiter.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)
    assert rate_limiter._get_state('z1', 'foo') == approx((t0, 1), abs=0.05)

    time.sleep(0.1)
    assert rate_limiter.request(k1='foo') == (True, 0)
    t1 = _redis_time(redis)
    assert rate_limiter._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05)

    time.sleep(0.1)
    assert rate_limiter.request(k1='foo') == (False, None)
    assert rate_limiter._get_state('z1', 'foo') == \
        approx((t1, 1.9), abs=0.05), 'not changed'


def test_state_delay(redis, rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1), delay=1))

    assert rate_limiter.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)
    assert rate_limiter._get_state('z1', 'foo') == approx((t0, 1), abs=0.05)

    time.sleep(0.1)
    assert rate_limiter.request(k1='foo') == (True, approx(0.9, abs=0.05))
    t1 = _redis_time(redis)
    assert rate_limiter._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05)

    time.sleep(0.1)
    assert rate_limiter.request(k1='foo') == (False, None)
    assert rate_limiter._get_state('z1', 'foo') == \
        approx((t1, 1.9), abs=0.05), 'not changed'


@pytest.mark.parametrize('codec', ('json', 'struct'))
def test_tx_script_interoperable(
        redis, redis_version_check, key_format, codec):

    redis_version_check(RedisScriptRateLimiter.MIN_REDIS_VERSION)
    srl = RedisScriptRateLimiter(redis, key_format=key_format, codec=codec)
    trl = RedisTransactionalRateLimiter(redis, key_format=key_format,
                                        codec=codec)

    limit = RateLimit(Zone('z1', 5), delay=5)
    srl.configure(k1=limit)
    trl.configure(k1=limit)

    assert srl.request(k1='foo') == (True, 0)
    assert trl.request(k1='foo') == (True, approx(1/5, abs=0.05))
    assert srl.request(k1='foo') == (True, approx(2/5, abs=0.05))
    t = _redis_time(redis)

    assert srl._get_state('z1', 'foo') == approx((t, 3), abs=0.05)
    assert trl._get_state('z1', 'foo') == approx((t, 3), abs=0.05)
