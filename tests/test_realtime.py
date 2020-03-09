"""Realtime rate limiting tests."""

import sched
import threading
import time

import pytest
from pytest import approx

from redbucket import (InMemoryRateLimiter, RedisScriptRateLimiter,
                       RedisTransactionalRateLimiter, RateLimit, Zone)


@pytest.fixture
def in_memory_rate_limiter():
    return InMemoryRateLimiter()


@pytest.fixture
def redis_tx_rate_limiter(redis, key_format):
    return RedisTransactionalRateLimiter(redis, key_format=key_format)


@pytest.fixture
def redis_script_rate_limiter(redis, redis_version_check, key_format):
    redis_version_check(RedisScriptRateLimiter.MIN_REDIS_VERSION)
    return RedisScriptRateLimiter(redis, key_format=key_format)


@pytest.fixture(params=('in_memory', 'redis_tx', 'redis_script'))
def rate_limiter(request):
    return request.getfixturevalue(f'{request.param}_rate_limiter')


def test_basic(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 5)))

    results = [None] * 12

    def req(i):
        results[i] = rate_limiter.request(k1='foo')

    sch = sched.scheduler()
    for i in range(12):
        sch.enter(0.1 + i/12, 0, req, (i,))
    sch.run()

    accepted = [int(s) for s, d in results]
    assert accepted == [1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0]


def test_burst(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 5), burst=2))

    results = [None] * 12

    def req(i):
        results[i] = rate_limiter.request(k1='foo')

    sch = sched.scheduler()
    for i in range(12):
        sch.enter(0.1 + i/12, 0, req, (i,))
    sch.run()

    accepted = [int(s) for s, d in results]
    assert accepted == [1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0]


def test_delay(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 5), delay=2))

    results = [None] * 12

    def req(i):
        results[i] = rate_limiter.request(k1='foo')

    sch = sched.scheduler()
    for i in range(12):
        sch.enter(0.1 + i/12, 0, req, (i,))
    sch.run()

    accepted = [int(s) for s, d in results]
    assert accepted == [1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0]

    dreq = [i/12 + d for i, (s, d) in enumerate(results) if s]
    assert dreq == approx([0, 1/5, 2/5, 3/5, 4/5, 1, 6/5], abs=0.05)


def test_burst_delay(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 5), burst=1, delay=1))

    results = [None] * 12

    def req(i):
        results[i] = rate_limiter.request(k1='foo')

    sch = sched.scheduler()
    for i in range(12):
        sch.enter(0.1 + i/12, 0, req, (i,))
    sch.run()

    accepted = [int(s) for s, d in results]
    assert accepted == [1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 0]

    dreq = [i/12 + d for i, (s, d) in enumerate(results) if s]
    assert dreq == approx([0, 1/12, 1/5, 2/5, 3/5, 4/5, 1], abs=0.05)


def test_multi_zone(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1), burst=4),
                           k2=RateLimit(Zone('z2', 5), delay=2))

    results = [None] * 12

    def req(i):
        results[i] = rate_limiter.request(k1='foo', k2='bar')

    sch = sched.scheduler()
    for i in range(12):
        sch.enter(0.1 + i/12, 0, req, (i,))
    sch.run()

    accepted = [int(s) for s, d in results]
    assert accepted == [1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0]

    dreq = [i/12 + d for i, (s, d) in enumerate(results) if s]
    assert dreq == approx([0, 1/5, 2/5, 3/5, 4/5], abs=0.05)


def test_multithreaded(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 7)))

    tstamps = [[], [], []]
    start = time.monotonic() + 0.1
    end = start + .95

    def thread_fn(i):
        time.sleep(max(start - time.monotonic(), 0))
        while time.monotonic() < end:
            s, d = rate_limiter.request(k1='foo')
            if s:
                tstamps[i].append(time.monotonic())
            time.sleep(0)

    threads = [threading.Thread(target=thread_fn, args=(i,)) for i in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    all_ts = sorted(tstamps[0] + tstamps[1] + tstamps[2])
    stime = all_ts[0]
    for i in range(len(all_ts)):
        all_ts[i] -= stime
    assert all_ts == approx([0, 1/7, 2/7, 3/7, 4/7, 5/7, 6/7], abs=0.05)


def test_request_invalid_key(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1)))

    with pytest.raises(KeyError) as ei:
        rate_limiter.request(k2='bar')

    assert str(ei.value) == repr('k2')


def test_request_no_keys(rate_limiter):
    rate_limiter.configure(k1=RateLimit(Zone('z1', 1)))
    assert rate_limiter.request() == (True, 0)
