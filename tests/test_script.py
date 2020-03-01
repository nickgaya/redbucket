from unittest.mock import NonCallableMock

import pytest
from redis import Redis

from redbucket.script import RedisScriptRateLimiter


def test_script_old_redis_version():
    mock_redis = NonCallableMock(name='redis', spec=Redis)
    mock_redis.info.return_value = {'redis_version': '2.6.17'}

    with pytest.raises(RuntimeError) as e:
        RedisScriptRateLimiter(mock_redis)

    assert str(e.value) == "Redis server has version 2.6.17. This " \
        "implementation requires version 3.2 or greater."
