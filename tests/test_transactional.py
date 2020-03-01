from unittest.mock import ANY, NonCallableMock, call

import pytest
from pytest import approx
from redis.client import Pipeline, Redis

from redbucket.codecs import Codec
from redbucket.data import RateLimit, State, Zone
from redbucket.transactional import RedisTransactionalRateLimiter

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


def _to_redis_time(timestamp):
    s = int(timestamp)
    us = int(timestamp % 1 * 1000000)
    return s, us


class DummyCodec(Codec):
    def encode(self, state):
        return state

    def decode(self, raw_state):
        return raw_state or None


def test_transactional_mock_redis(mock_redis, mock_pipeline):
    rl = RedisTransactionalRateLimiter(mock_redis, codec=DummyCodec())
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
    mock_pipeline.mget.return_value = [State(t0, 1)]
    mock_pipeline.time.return_value = _to_redis_time(t2)
    assert rl.request(k1='foo') == (False, None)

    t3 = T0 + 0.51
    mock_pipeline.time.return_value = _to_redis_time(t3)
    assert rl.request(k1='foo') == (True, 0)

    assert mock_redis.mock_calls == [
        call.transaction(ANY, 'redbucket:z1:foo', value_from_callable=True),
        call.transaction(ANY, 'redbucket:z1:bar', 'redbucket:z2:baz',
                         value_from_callable=True),
        call.transaction(ANY, 'redbucket:z1:foo', value_from_callable=True),
        call.transaction(ANY, 'redbucket:z1:foo', value_from_callable=True),
    ]

    assert mock_pipeline.mock_calls == [
        # request 1
        call.watch('redbucket:z1:foo'),
        call.mget(['redbucket:z1:foo']),
        call.time(),
        call.multi(),
        call.setex('redbucket:z1:foo', 60, State(approx(t0), 1)),
        call.execute(),
        # request 2
        call.watch('redbucket:z1:bar', 'redbucket:z2:baz'),
        call.mget(['redbucket:z1:bar', 'redbucket:z2:baz']),
        call.time(),
        call.multi(),
        call.setex('redbucket:z1:bar', 60, State(approx(t1), 1)),
        call.setex('redbucket:z2:baz', 10, State(approx(t1), 1)),
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
        call.setex('redbucket:z1:foo', 60, State(approx(t3), 1)),
        call.execute(),
    ]
