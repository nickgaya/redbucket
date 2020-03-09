import os

import pytest
from redis import Redis

from redbucket.base import get_redis_version


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


@pytest.fixture(scope='session')
def redis_version(redis):
    return get_redis_version(redis)


@pytest.fixture(scope='session')
def redis_version_check(redis_version):
    def check(min_version):
        if redis_version < min_version:
            rv = '.'.join(map(str, redis_version))
            mv = '.'.join(map(str, min_version))
            pytest.skip(f"redis version {rv} < {mv}")

    return check
