# Red Bucket

Python rate limiting library using Redis for shared state.

## Installation

To install the latest released version:

    pip install redbucket

To install the current development version from the master branch on GitHub:

    pip install -U git+https://github.com/nickgaya/redbucket.git

## Usage

The following snippet configures a rate limiter with two rate limiting zones:

```python3
from redbucket import RedisRateLimiter, RateLimit, Zone
from redis import Redis


# Accept up to 5 requests per user per second.
# Allow bursts of up to 10 requests.
user_zone = Zone('user', rate=5)
user_limit = RateLimit(user_zone, burst=10)

# Accept up to 20 requests per IP per second.
# Allow up to 10 excess requests with a delay.
ip_zone = Zone('ip', rate=20)
ip_limit = RateLimit(ip_zone, delay=10)

redis = Redis()
rate_limiter = RedisRateLimiter(redis)
rate_limiter.configure(user=user_limit, ip=ip_limit)
```

We can now use the rate limiter as follows:

```python3
def example_operation(user, ip_address):
    response = rate_limiter.request(user=user, ip=ip_address)
    if not response.accepted:
        raise Exception("Rate limit exceeded")  # Reject request
    if response.delay > 0:
        sleep(response.delay)  # Wait for delay seconds
    ...  # Perform operation
```

Note that we don't have to specify a key for every zone. For example, we could
exclude certain IP addresses from IP rate limiting while still applying the
user rate limit, as follows:

```python3
def example_operation(user, ip_address):
    if is_whitelisted(ip_address):
        response = rate_limiter.acquire(user=user)
    else:
        response = rate_limiter.acquire(user=user, ip=ip_address)
    ...
```

### Implementations

The default `RedisRateLimiter` uses Redis's Lua script engine to atomically
update rate limiter state. This implementation requires Redis 3.2 or greater.
For older Redis versions, you can use the `RedisTransactionalRateLimiter`.

Where supported, the script-based implementation is recommended as it handles
each rate limiting request in a single round-trip to the Redis server, whereas
the transactional implementation performs several consecutive Redis commands
per request.

### State encoding

By default, rate limiter state is stored in Redis using a packed binary
representation. You can switch to JSON for a less efficient but more
human-readable encoding.

    rate_limiter = RedisRateLimiter(redis, codec='json')

## Rate limiting model

Red Bucket uses a rate limiting model inspired by [Nginx][rate-limiting-nginx].
Rate limiting state is stored in one or more **zones**. Each zone has a name
and a base **rate**. A zone represents a namespace of rate limiting **keys**. A
**rate limit** references a zone along with two parameters, **burst** and
**delay**. A **rate limiter** references one or more rate limits.

To apply rate limiting to an operation, the application makes a **request** to
the rate limiter by specifying a key for each desired rate limit. The rate
limiter evaluates each rate limit to determine whether to reject, delay, or
immediately accept the request. If using multiple rate limits, the most
restrictive outcome will be applied.

For a rate limit with base rate <i>r</i>, burst value <i>b</i>, and delay value
<i>d</i>, the rate limiter maintains a virtual counter for each key that
continuously increases at a rate of <i>r</i> requests per second up to a
maximum value of
<span style="white-space: nowrap;"><i>b</i> + 1</span>. When a request arrives,
the rate limiter checks the current value of the counter <i>v</i>. If
<span style="white-space: nowrap;"><i>v</i> &minus; 1 &ge; 0</span>, the rate
limiter decrements the counter by 1 and accepts the request immediately. If
<span style="white-space: nowrap;"><i>v</i> &minus; 1 &ge; &minus;<i>d</i></span>,
the rate limiter decrements the counter by 1 and accepts the request after a
delay of
<span style="white-space: nowrap;">(<i>v</i> &minus; 1) / <i>r</i></span>
seconds. Otherwise, *i.e.* if
<span style="white-space: nowrap;"><i>v</i> &minus; 1 &lt; &minus;<i>d</i></span>,
the rate limiter rejects the request.

In practice, this means that from an initial idle state for a given key, the
rate limiter will allow a burst of
<span style="white-space: nowrap;"><i>b</i> + 1</span> requests immediately,
throttle the next <i>d</i> requests to the desired rate, and reject any further
requests past the limit.

[rate-limiting-nginx]: https://www.nginx.com/blog/rate-limiting-nginx/ "Rate Limiting with NGINX"

### Comparison with Nginx

As noted above, Red Bucket's rate limiting model is inspired by Nginx and
uses a similar algorithm. However, the way burst and delay are specified is a
little different. The following configuration examples illustrate the
difference.

* Basic rate limiting

    ```nginx
    # nginx
    limit_req zone=mylimit;
    ```
    ```python3
    # redbucket
    RateLimit(zone=mylimit)
    ```

* Burst with delay

    ```nginx
    # nginx
    limit_req zone=mylimit burst=20;
    ```
    ```python3
    # redbucket
    RateLimit(zone=mylimit, delay=20)
    ```

* Burst with no delay

    ```nginx
    # nginx
    limit_req zone=mylimit burst=20 nodelay;
    ```
    ```python3
    # redbucket
    RateLimit(zone=mylimit, burst=20)
    ```

* Two-stage rate limiting

    ```nginx
    # nginx
    limit_req zone=ip burst=12 delay=8;
    ```
    ```python3
    # redbucket
    RateLimit(zone=mylimit, burst=8, delay=4)
    ```

## Development

This project uses Tox to manage virtual environments for unit tests and other
checks. Unit tests are written using the Pytest framework.

The unit tests require a Redis instance. By default, the tests attempt to
connect to port 6379 of localhost. This can be overridden by setting the
`REDIS_URL` environment variable.

    export REDIS_URL=redis://localhost:6379

To start a Redis Docker container for running the tests, you can use the
*docker_redis.sh* script. For example, to run the tests against a Docker redis
instance, you can run:

    ./docker_redis.sh tox

You can also run the script without a command and execute output to set
environment variables in your current shell.

    eval "$(./docker_redis.sh)"

By default, the script uses the `redis:alpine` image. You can supply a
different tag for the `redis` image with the `-t` flag, or a different image
name with `-i`.
