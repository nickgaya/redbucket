"""Redis-based rate limiter implementation."""

import json
from string import Formatter

from redbucket.base import RateLimiter

# JSON keys for state encoding
TIMESTAMP_KEY = 't'
VALUE_KEY = 'v'


class RedisRateLimiter(RateLimiter):
    """
    Redis-based rate limiter.

    Zone state is stored in Redis. The implementation uses Redis transactions
    to atomically update zone state for each request.
    """

    def __init__(self, redis, key_format='redbucket:{zone}:{key}'):
        """
        Initialize a RedisRateLimiter instance.

        :param redis: Redis client
        :param key_format: Redis key format. Must contain replacement fields
            'zone' and 'key'.
        """
        super(RedisRateLimiter, self).__init__()
        self._redis = redis
        self._key_format = _validate_key_format(key_format)

    def _redis_key(self, zone, key):
        return self._key_format.format(zone=zone, key=key)

    def _request(self, keys):
        limits = []
        rkeys = []
        for lname, key in keys.items():
            limit = self._rate_limits[lname]
            limits.append(limit)
            rkeys.append(self._redis_key(limit.zone.name, key))

        def tx_fn(pipeline):
            """Code to be executed within a Redis transaction."""
            rstates = pipeline.mget(rkeys)

            t_s, t_us = pipeline.time()
            t1 = t_s + t_us / 1000000

            delay = 0
            states = []
            for limit, rstate in zip(limits, rstates):
                t0, v0 = _decode(rstate) or (t1, 0)
                v1 = max(v0 - (t1 - t0) * limit.zone.rate, 0) + 1
                c = limit.burst + 1 - v1
                if c < -limit.delay:
                    pipeline.unwatch()
                    return False, None
                if c < 0:
                    delay = max(delay, -c/limit.zone.rate)
                states.append((t1, v1))

            pipeline.multi()
            for limit, rkey, state in zip(limits, rkeys, states):
                pipeline.setex(rkey, limit.zone.expiry, _encode(*state))

            return True, delay

        return self._redis.transaction(tx_fn, *rkeys, value_from_callable=True)

    def _get_state(self, zname, key):
        return _decode(self._redis.get(self._redis_key(zname, key)))


def _validate_key_format(format_string):
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


def _decode(rstate):
    """
    Decode state from bytes.

    :param rstate: Encoded state as bytes, or None
    :return: A state pair (t, v) or None
    """
    if not rstate:
        return None
    d = json.loads(rstate.decode('utf8'))
    return d[TIMESTAMP_KEY], d[VALUE_KEY]


def _encode(t, v):
    """
    Encode state to bytes.

    :param t: Timestamp value
    :param v: Rate limit value
    :return: Encoded state as bytes.
    """
    return json.dumps({
        TIMESTAMP_KEY: t,
        VALUE_KEY: v,
    }, separators=(',', ':')).encode('utf8')
