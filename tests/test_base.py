import pytest

from redbucket.base import RateLimit, RateLimiter, Zone


class DummyRateLimiter(RateLimiter):
    """Dummy rate limiter used to test abstract base class functionality."""

    def _request(self, keys):
        for lname in keys:
            self._rate_limits[lname]
        return False, None


def test_conflicting_rate_limits():
    z1 = Zone('z1', 1)
    z2 = Zone('z2', 2)
    l1 = RateLimit(z1)
    l2 = RateLimit(z2, burst=3)
    l3 = RateLimit(z1, delay=1)

    rl = DummyRateLimiter()
    with pytest.raises(ValueError) as ei:
        rl.configure(k1=l1, k2=l2, k3=l3)

    assert str(ei.value) == "Multiple rate limits for zone 'z1'"


def test_reconfigure():
    rl = DummyRateLimiter()
    rl.configure(k1=RateLimit(Zone('z1', 1)))

    with pytest.raises(RuntimeError) as ei:
        rl.configure(k2=RateLimit(Zone('z2', 2)))

    assert str(ei.value) == "Rate limiter already configured"


def test_not_configured():
    rl = DummyRateLimiter()

    with pytest.raises(RuntimeError) as ei:
        rl.request(k1='foo')

    assert str(ei.value) == "Rate limiter not configured"


def test_expiry_warning():
    z1 = Zone('z1', 2, 5)
    l1 = RateLimit(z1, burst=4, delay=6)
    rl = DummyRateLimiter()

    with pytest.warns(UserWarning) as rec:
        rl.configure(k1=l1)

    assert len(rec) == 1
    assert str(rec[0].message) == ("Expiry for zone 'z1' is less than "
                                   "recommended minimum for limit 'k1': "
                                   "expiry=5, recommended=6")