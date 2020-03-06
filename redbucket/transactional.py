"""Transactional Redis-based rate limiter implementation."""

from typing import Any, List, Mapping, Optional, Union

from redis import Redis
from redis.client import Pipeline

from redbucket.base import RedisRateLimiter
from redbucket.codecs import DEFAULT_CODEC, Codec, get_codec
from redbucket.data import RateLimit, Response, State

__all__ = ('RedisTransactionalRateLimiter',)


class RedisTransactionalRateLimiter(RedisRateLimiter):
    """
    Transactional Redis-based rate limiter.

    Zone state is stored in Redis. The implementation uses Redis transactions
    to atomically update zone state for each request.
    """

    def __init__(self, redis: Redis,
                 key_format: str = 'redbucket:{zone}:{key}',
                 codec: Union[str, Codec] = DEFAULT_CODEC) -> None:
        """
        Initialize a RedisTransactionalRateLimiter instance.

        :param redis: Redis client
        :param key_format: Redis key format. Must contain replacement fields
            'zone' and 'key'.
        :param codec: Codec name or instance
        """
        super(RedisTransactionalRateLimiter, self).__init__(redis, key_format)
        self._codec: Codec = \
            get_codec(codec) if isinstance(codec, str) else codec

    def _request(self, keys: Mapping[str, Any]) -> Response:
        if not keys:
            return Response(True, 0)

        limits: List[RateLimit] = []
        rkeys: List[str] = []
        for lname, key in keys.items():
            limit = self._rate_limits[lname]
            limits.append(limit)
            rkeys.append(self._redis_key(limit.zone.name, key))

        def tx_fn(pipeline: Pipeline) -> Response:
            """Code to be executed within a Redis transaction."""
            rstates: List[Optional[bytes]] = pipeline.mget(rkeys)

            t_s: int
            t_us: int
            t_s, t_us = pipeline.time()
            t1 = t_s + t_us / 1000000

            delay: float = 0
            states: List[State] = []
            for limit, rstate in zip(limits, rstates):
                t0, v0 = self._codec.decode(rstate) or (t1, 0)
                v1 = max(v0 - (t1 - t0) * limit.zone.rate, 0) + 1
                c = limit.burst + 1 - v1
                if c < -limit.delay:
                    pipeline.unwatch()
                    return Response(False, None)
                if c < 0:
                    delay = max(delay, -c/limit.zone.rate)
                states.append(State(t1, v1))

            pipeline.multi()
            for limit, rkey, state in zip(limits, rkeys, states):
                pipeline.setex(rkey, limit.zone.expiry,
                               self._codec.encode(state))

            return Response(True, delay)

        response: Response = self._redis.transaction(
            tx_fn, *rkeys, value_from_callable=True)
        return response

    def _get_state(self, zname: Any, key: Any) -> Optional[State]:
        return self._codec.decode(self._redis.get(self._redis_key(zname, key)))
