import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from aiohttp import web
from redbucket import RateLimit, RedisScriptRateLimiter, Zone
from redis import Redis

executor = ThreadPoolExecutor()

redis = Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost'))
rate_limiter = RedisScriptRateLimiter(redis)
rate_limiter.configure(
    ip=RateLimit(Zone('ip', 1), delay=3),
    user=RateLimit(Zone('user', 1/5), burst=5),
)

async def rate_limit(ip, user):
    kwargs = {'ip': ip}
    if user:
        kwargs['user'] = user
    # Use executor for non-blocking request to rate limiter
    success, delay = await asyncio.wrap_future(executor.submit(
        rate_limiter.request, **kwargs))
    if success:
        await asyncio.sleep(delay)
    return success

async def handle(request):
    user = request.query.get('user')
    if await rate_limit(request.remote, user):
        return web.Response(text=f'Hello, {user}' if user else 'Hello')
    else:
        return web.Response(status=429, text='Rate limit exceeded')

app = web.Application()
app.add_routes([web.get('/', handle)])

if __name__ == '__main__':
    web.run_app(app, host='localhost')
