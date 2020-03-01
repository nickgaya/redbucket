import time

import pytest

from redbucket.codecs import get_codec
from redbucket.data import State


@pytest.fixture(params=('json', 'struct'))
def codec(request):
    return get_codec(request.param)


def test_encode_decode(codec):
    state = State(time.time(), 1.23)
    data = codec.encode(state)
    assert isinstance(data, bytes)
    decoded = codec.decode(data)
    assert isinstance(decoded, State)
    assert decoded == pytest.approx(state)


def test_decode_None(codec):
    assert codec.decode(None) is None


def test_decode_empty(codec):
    assert codec.decode(b'') is None
