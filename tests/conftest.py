import os

import pytest
from redis import Redis


@pytest.fixture(scope='session')
def redis():
    redis = Redis.from_url(
        os.environ.get('REDIS_URL', 'redis://localhost'))
    redis.ping()
    redis.setnx('rb:test_id', 0)
    assert redis.expire('rb:test_id', 300)
    return redis


@pytest.fixture
def key_format(redis):
    id_ = redis.incr('rb:test_id')
    return f'rb:{id_}:{{zone}}:{{key}}'
