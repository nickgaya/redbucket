"""Redis Lua script-based rate limiter implementation."""

import string
import textwrap
from typing import Any, List, Mapping, Optional, Union

from redis import Redis
from redis.client import Script

from redbucket.base import RedisRateLimiter
from redbucket.codecs import DEFAULT_CODEC, LuaCodec, get_codec, lua_escape
from redbucket.data import RateLimit, Response, State

__all__ = ('RedisScriptRateLimiter',)

LUA_TEMPLATE = string.Template("""\
assert(redis.replicate_commands(), "failed to enable effects replication")
local limits = ${limits}
local codec = {}
function codec.encode(timestamp, value)
${encode}
end
function codec.decode(raw_state)
${decode}
end
local rstates = redis.call("MGET", unpack(KEYS))
local rt = redis.call("TIME")
local t1 = rt[1] + rt[2] / 1000000
local delay = 0
local nstates = {}
for i, rkey in ipairs(KEYS) do
  local lname = ARGV[i]
  local limit = limits[lname]
  local t0
  local v0
  local rstate = rstates[i]
  if rstate then
    t0, v0 = codec.decode(rstate)
  else
    t0 = t1
    v0 = 0
  end
  local v1 = math.max(v0 - (t1 - t0) * limit.rate, 0) + 1
  local x = limit.burst + 1 - v1
  if x < -limit.delay then
    return false
  end
  if x < 0 then
    delay = math.max(delay, -x/limit.rate)
  end
  nstates[i] = {t1, v1, limit.expiry}
end
for i, rkey in ipairs(KEYS) do
    local nstate = nstates[i]
    local encoded = codec.encode(nstate[1], nstate[2])
    redis.call("SETEX", rkey, nstate[3], encoded)
end
return tostring(delay)
""")

LUA_GET_TEMPLATE = string.Template("""\
local codec = {}
function codec.decode(raw_state)
${decode}
end
local rstate = redis.call("GET", KEYS[1])
if rstate then
    local timestamp, value = codec.decode(rstate)
    return {tostring(timestamp), tostring(value)}
else
    return false
end
""")


class RedisScriptRateLimiter(RedisRateLimiter):
    """
    Redis script-based rate limiter.

    Zone state is stored in Redis. This implementation uses a Lua script to
    atomically update zone state for each request.
    """

    # Script effects replication was added in Redis 3.2
    MIN_REDIS_VERSION = (3, 2)

    def __init__(self, redis: Redis,
                 key_format: str = 'redbucket:{zone}:{key}',
                 codec: Union[str, LuaCodec] = DEFAULT_CODEC) -> None:
        """
        Initialize a RedisScriptRateLimiter instance.

        :param redis: Redis client
        :param key_format: Redis key format. Must contain replacement fields
            'zone' and 'key'.
        :param codec: Codec name
        """
        super(RedisScriptRateLimiter, self).__init__(redis, key_format)
        self._codec: LuaCodec = \
            get_codec(codec) if isinstance(codec, str) else codec

    def _configure(self, rate_limits: Mapping[str, RateLimit]) -> None:
        limits = '{' + ', '.join(
            f'["{lua_escape(lname)}"] = {{'
            f'["rate"] = {limit.zone.rate}, '
            f'["burst"] = {limit.burst}, '
            f'["delay"] = {limit.delay}, '
            f'["expiry"] = {limit.zone.expiry}'
            f'}}' for lname, limit in rate_limits.items()) + '}'
        encode = textwrap.indent(self._codec.lua_encode().rstrip('\n'), '  ')
        decode = textwrap.indent(self._codec.lua_decode().rstrip('\n'), '  ')
        script = LUA_TEMPLATE.substitute(
            limits=limits, encode=encode, decode=decode)
        self._script: Script = self._redis.register_script(script)

        get_script = LUA_GET_TEMPLATE.substitute(decode=decode)
        self._get_script: Script = self._redis.register_script(get_script)

    def _request(self, keys: Mapping[str, Any]) -> Response:
        if not keys:
            return Response(True, 0)

        rkeys: List[str] = []
        args: List[str] = []
        for lname, key in keys.items():
            limit = self._rate_limits[lname]
            rkeys.append(self._redis_key(limit.zone.name, key))
            args.append(lname)

        result = self._script(keys=rkeys, args=args)
        if result:
            return Response(True, float(result))
        else:
            return Response(False, None)

    def _get_state(self, zname: Any, key: Any) -> Optional[State]:
        result = self._get_script(keys=[self._redis_key(zname, key)])
        return State(*map(float, result)) if result else None
