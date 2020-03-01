import time
from unittest import mock

import pytest
from pytest import approx

from redbucket.data import RateLimit, Zone
from redbucket.in_memory import InMemoryRateLimiter

T0 = 123.4


@pytest.fixture
def mock_time(monkeypatch):
    mtime = mock.Mock(name='time', wraps=time)
    monkeypatch.setattr('redbucket.in_memory.time', mtime)
    return mtime


def test_request_initial(mock_time):
    z1 = Zone('z1', 1)
    z2 = Zone('z2', 2)

    l1 = RateLimit(z1)
    l2 = RateLimit(z2)

    rl = InMemoryRateLimiter()
    rl.configure(k1=l1, k2=l2)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo') == (True, 0)

    mock_time.monotonic.return_value = t1 = T0 + 0.1
    assert rl.request(k1='bar', k2='baz') == (True, 0)

    assert rl._zones['z1'].state == {'foo': (t0, 1), 'bar': (t1, 1)}
    assert rl._zones['z2'].state == {'baz': (t1, 1)}


def test_request_basic(mock_time):
    z1 = Zone('z1', 2)
    l1 = RateLimit(z1)
    rl = InMemoryRateLimiter()
    rl.configure(k1=l1)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)

    mock_time.monotonic.return_value = t0 + 0.3
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t0, 1), 'not changed'

    mock_time.monotonic.return_value = t1 = t0 + 0.51
    assert rl.request(k1='foo') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t1, 1)


def test_request_burst(mock_time):
    z1 = Zone('z1', 2)
    l1 = RateLimit(z1, burst=2)
    rl = InMemoryRateLimiter()
    rl.configure(k1=l1)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)

    mock_time.monotonic.return_value = t1 = t0 + 0.2
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6))

    mock_time.monotonic.return_value = t0 + 0.4
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6)), \
        'not changed'

    mock_time.monotonic.return_value = t2 = t0 + 0.51
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98))

    mock_time.monotonic.return_value = t0 + 0.8
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98)), \
        'not changed'

    mock_time.monotonic.return_value = t3 = t0 + 1.6
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t3, approx(2.8))

    mock_time.monotonic.return_value = t4 = t0 + 3.3
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t4, 3)


def test_request_delay(mock_time):
    z1 = Zone('z1', 2)
    l1 = RateLimit(z1, delay=2)
    rl = InMemoryRateLimiter()
    rl.configure(k1=l1)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)

    mock_time.monotonic.return_value = t1 = t0 + 0.2
    assert rl.request(k1='foo') == (True, approx(0.3))
    assert rl.request(k1='foo') == (True, approx(0.8))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6))

    mock_time.monotonic.return_value = t0 + 0.4
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6)), \
        'not changed'

    mock_time.monotonic.return_value = t2 = t0 + 0.51
    assert rl.request(k1='foo') == (True, approx(0.99))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98))

    mock_time.monotonic.return_value = t0 + 0.8
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98)), \
        'not changed'

    mock_time.monotonic.return_value = t3 = t0 + 1.6
    assert rl.request(k1='foo') == (True, approx(0.4))
    assert rl.request(k1='foo') == (True, approx(0.9))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t3, approx(2.8))

    mock_time.monotonic.return_value = t4 = t0 + 3.3
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, approx(0.5))
    assert rl.request(k1='foo') == (True, approx(1.0))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t4, 3)


def test_request_burst_delay(mock_time):
    z1 = Zone('z1', 2)
    l1 = RateLimit(z1, burst=1, delay=1)
    rl = InMemoryRateLimiter()
    rl.configure(k1=l1)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)

    mock_time.monotonic.return_value = t1 = t0 + 0.2
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, approx(0.3))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6))

    mock_time.monotonic.return_value = t0 + 0.4
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t1, approx(2.6)), \
        'not changed'

    mock_time.monotonic.return_value = t2 = t0 + 0.51
    assert rl.request(k1='foo') == (True, approx(0.49))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98))

    mock_time.monotonic.return_value = t0 + 0.8
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.98)), \
        'not changed'

    mock_time.monotonic.return_value = t3 = t0 + 1.6
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, approx(0.4))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t3, approx(2.8))

    mock_time.monotonic.return_value = t4 = t0 + 3.3
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k1='foo') == (True, approx(0.5))
    assert rl.request(k1='foo') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t4, 3)


def test_request_multi_zone(mock_time):
    z1 = Zone('z1', 1)
    z2 = Zone('z2', 1/.8)

    l1 = RateLimit(z1)
    l2 = RateLimit(z2)

    rl = InMemoryRateLimiter()
    rl.configure(k1=l1, k2=l2)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo', k2='bar') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)
    assert rl._zones['z2'].state['bar'] == (t0, 1)

    mock_time.monotonic.return_value = t0 + 0.1
    assert rl.request(k1='foo') == (False, None)
    assert rl.request(k2='bar') == (False, None)
    assert rl.request(k1='foo', k2='bar') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t0, 1), 'not changed'
    assert rl._zones['z2'].state['bar'] == (t0, 1), 'not changed'

    mock_time.monotonic.return_value = t1 = t0 + 0.81
    assert rl.request(k1='foo', k2='bar') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t0, 1), 'not changed'
    assert rl._zones['z2'].state['bar'] == (t0, 1), 'not changed'

    assert rl.request(k1='foo') == (False, None)
    assert rl.request(k2='bar') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1), 'not changed'
    assert rl._zones['z2'].state['bar'] == (t1, 1)

    mock_time.monotonic.return_value = t2 = t0 + 1.01
    assert rl.request(k1='foo', k2='bar') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t0, 1), 'not changed'
    assert rl._zones['z2'].state['bar'] == (t1, 1), 'not changed'

    assert rl.request(k1='foo') == (True, 0)
    assert rl.request(k2='bar') == (False, None)
    assert rl._zones['z1'].state['foo'] == approx((t2, 1))
    assert rl._zones['z2'].state['bar'] == approx((t1, 1)), 'not changed'

    mock_time.monotonic.return_value = t0 + 1.2
    assert rl.request(k1='foo') == (False, None)
    assert rl.request(k2='bar') == (False, None)
    assert rl.request(k1='foo', k2='bar') == (False, None)
    assert rl._zones['z1'].state['foo'] == approx((t2, 1)), 'not changed'
    assert rl._zones['z2'].state['bar'] == approx((t1, 1)), 'not changed'

    mock_time.monotonic.return_value = t3 = t0 + 2.02
    assert rl.request(k1='foo', k2='bar') == (True, 0)
    assert rl._zones['z1'].state['foo'] == approx((t3, 1))
    assert rl._zones['z2'].state['bar'] == approx((t3, 1))


def test_request_multi_zone_burst_delay(mock_time):
    z1 = Zone('z1', 1)
    z2 = Zone('z2', 2)
    z3 = Zone('z3', 3)

    l1 = RateLimit(z1, burst=10)
    l2 = RateLimit(z2, delay=2)
    l3 = RateLimit(z3, burst=1, delay=1)

    rl = InMemoryRateLimiter()
    rl.configure(k1=l1, k2=l2, k3=l3)

    mock_time.monotonic.return_value = t0 = T0
    assert rl.request(k1='foo', k2='bar', k3='baz') == (True, 0)
    assert rl._zones['z1'].state['foo'] == (t0, 1)
    assert rl._zones['z2'].state['bar'] == (t0, 1)
    assert rl._zones['z3'].state['baz'] == (t0, 1)

    mock_time.monotonic.return_value = t1 = t0 + 0.1
    assert rl.request(k1='foo', k2='bar', k3='baz') == (True, approx(0.4))
    assert rl._zones['z1'].state['foo'] == (t1, approx(1.9))
    assert rl._zones['z2'].state['bar'] == (t1, approx(1.8))
    assert rl._zones['z3'].state['baz'] == (t1, approx(1.7))

    mock_time.monotonic.return_value = t2 = t0 + 0.2
    assert rl.request(k1='foo', k2='bar', k3='baz') == (True, approx(0.8))
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.8))
    assert rl._zones['z2'].state['bar'] == (t2, approx(2.6))
    assert rl._zones['z3'].state['baz'] == (t2, approx(2.4))

    mock_time.monotonic.return_value = t3 = t0 + 0.4
    assert rl.request(k1='foo', k2='bar', k3='baz') == (False, None)
    assert rl._zones['z1'].state['foo'] == (t2, approx(2.8)), \
        'not changed'
    assert rl._zones['z2'].state['bar'] == (t2, approx(2.6)), \
        'not changed'
    assert rl._zones['z3'].state['baz'] == (t2, approx(2.4)), \
        'not changed'

    assert rl.request(k1='foo', k3='baz') == (True, approx(0.8 / 3))
    assert rl._zones['z1'].state['foo'] == (t3, approx(3.6))
    assert rl._zones['z2'].state['bar'] == (t2, approx(2.6)), \
        'not changed'
    assert rl._zones['z3'].state['baz'] == (t3, approx(2.8))

    mock_time.monotonic.return_value = t4 = t0 + 0.8
    assert rl.request(k1='foo', k2='bar', k3='baz') == (True, approx(0.7))
    assert rl._zones['z1'].state['foo'] == (t4, approx(4.2))
    assert rl._zones['z2'].state['bar'] == (t4, approx(2.4))
    assert rl._zones['z3'].state['baz'] == (t4, approx(2.6))
