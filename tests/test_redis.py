import json
import time
from unittest.mock import NonCallableMock, call

import pytest
from pytest import approx
from redis import Redis
from redis.client import Pipeline

from redbucket import RedisRateLimiter, RateLimit, Zone

T0 = 1582534960.134661


@pytest.fixture
def mock_pipeline():
    return NonCallableMock(name='pipeline', spec=Pipeline)


@pytest.fixture
def mock_redis(mock_pipeline):
    mock_redis = NonCallableMock(name='redis', spec=Redis)

    def transaction(func, *watches, value_from_callable=False):
        assert value_from_callable
        mock_pipeline.watch(*watches)
        result = func(mock_pipeline)
        mock_pipeline.execute()
        return result

    mock_redis.transaction.side_effect = transaction
    return mock_redis


def _redis_time(redis):
    s, us = redis.time()
    return s + us / 1000000


def _to_redis_time(timestamp):
    s = int(timestamp)
    us = int(timestamp % 1 * 1000000)
    return s, us


class EncodedState:
    def __init__(self, t, v):
        self.t = t
        self.v = v

    def __eq__(self, other):
        return json.loads(other.decode('utf8')) == {'t': self.t, 'v': self.v}

    def __repr__(self):
        return f'<t={self.t!r}, v={self.v!r}>'


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
        RedisRateLimiter(mock_redis, key_format=format_string)


@pytest.mark.parametrize('format_string', (
    '{zone}{key}',
    '{key}{zone}',
    '{zone}{key}{zone}',
    '{zone!r}{key}',
    '{{{zone}{key}}}',
))
def test_valid_key_format(mock_redis, format_string):
    RedisRateLimiter(mock_redis, key_format=format_string)


def test_request_mock_redis(mock_redis, mock_pipeline):
    rl = RedisRateLimiter(mock_redis)
    rl.configure(k1=RateLimit(Zone('z1', 2)),
                 k2=RateLimit(Zone('z2', 1, expiry=10)))

    t0 = T0
    mock_pipeline.mget.return_value = [None]
    mock_pipeline.time.return_value = _to_redis_time(t0)
    assert rl.request(k1='foo') == (True, 0)

    t1 = T0 + 0.1
    mock_pipeline.mget.return_value = [None, None]
    mock_pipeline.time.return_value = _to_redis_time(t1)
    assert rl.request(k1='bar', k2='baz') == (True, 0)

    t2 = T0 + 0.3
    mock_pipeline.mget.return_value = [
        json.dumps({'t': t0, 'v': 1}).encode('utf8')]
    mock_pipeline.time.return_value = _to_redis_time(t2)
    assert rl.request(k1='foo') == (False, None)

    t3 = T0 + 0.51
    mock_pipeline.time.return_value = _to_redis_time(t3)
    assert rl.request(k1='foo') == (True, 0)

    assert mock_pipeline.mock_calls == [
        # request 1
        call.watch('redbucket:z1:foo'),
        call.mget(['redbucket:z1:foo']),
        call.time(),
        call.multi(),
        call.setex('redbucket:z1:foo', 60, EncodedState(approx(t0), 1)),
        call.execute(),
        # request 2
        call.watch('redbucket:z1:bar', 'redbucket:z2:baz'),
        call.mget(['redbucket:z1:bar', 'redbucket:z2:baz']),
        call.time(),
        call.multi(),
        call.setex('redbucket:z1:bar', 60, EncodedState(approx(t1), 1)),
        call.setex('redbucket:z2:baz', 10, EncodedState(approx(t1), 1)),
        call.execute(),
        # request 3
        call.watch('redbucket:z1:foo'),
        call.mget(['redbucket:z1:foo']),
        call.time(),
        call.unwatch(),
        call.execute(),
        # request 4
        call.watch('redbucket:z1:foo'),
        call.mget(['redbucket:z1:foo']),
        call.time(),
        call.multi(),
        call.setex('redbucket:z1:foo', 60, EncodedState(approx(t3), 1)),
        call.execute(),
    ]


def test_state_initial(redis, key_format):
    rl = RedisRateLimiter(redis, key_format=key_format)
    rl.configure(k1=RateLimit(Zone('z1', 1)), k2=RateLimit(Zone('z2', 1)))

    assert rl.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)

    time.sleep(0.1)
    assert rl.request(k1='bar', k2='baz') == (True, 0)
    t1 = _redis_time(redis)

    assert redis.get(key_format.format(zone='z1', key='foo')) \
        == EncodedState(approx(t0), 1)
    assert redis.get(key_format.format(zone='z1', key='bar')) \
        == EncodedState(approx(t1), 1)
    assert redis.get(key_format.format(zone='z2', key='baz')) \
        == EncodedState(approx(t1), 1)


def test_state_burst(redis, key_format):
    rl = RedisRateLimiter(redis, key_format=key_format)
    rl.configure(k1=RateLimit(Zone('z1', 1), burst=1))

    assert rl.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)
    assert rl._get_state('z1', 'foo') == (approx(t0, abs=0.05), 1)

    time.sleep(0.1)
    assert rl.request(k1='foo') == (True, 0)
    t1 = _redis_time(redis)
    assert rl._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05)

    time.sleep(0.1)
    assert rl.request(k1='foo') == (False, None)
    assert rl._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05), \
        'not changed'


def test_state_delay(redis, key_format):
    rl = RedisRateLimiter(redis, key_format=key_format)
    rl.configure(k1=RateLimit(Zone('z1', 1), delay=1))

    assert rl.request(k1='foo') == (True, 0)
    t0 = _redis_time(redis)
    assert rl._get_state('z1', 'foo') == (approx(t0, abs=0.05), 1)

    time.sleep(0.1)
    assert rl.request(k1='foo') == (True, approx(0.9, abs=0.05))
    t1 = _redis_time(redis)
    assert rl._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05)

    time.sleep(0.1)
    assert rl.request(k1='foo') == (False, None)
    assert rl._get_state('z1', 'foo') == approx((t1, 1.9), abs=0.05), \
        'not changed'
