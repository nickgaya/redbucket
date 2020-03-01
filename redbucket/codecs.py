"""Classes for encoding rate limiter state as binary data."""

import json as _json
import struct
from abc import ABC, abstractmethod
from typing import Optional

from redbucket.base import State


class Codec(ABC):
    """Abstract codec base class."""

    @abstractmethod
    def encode(self, state: State) -> bytes:
        """
        Encode a state to bytes.

        :param state: State to encode
        :return: Encoded state as bytes.
        """
        ...

    @abstractmethod
    def decode(self, raw_state: Optional[bytes]) -> Optional[State]:
        """
        Decode a state from bytes.

        :param raw_state: Encoded state, or None.
        :return: Decoded state, or None.
        """
        ...


class JsonCodec(Codec):
    """
    Codec for encoding state to UTF8-encoded JSON data.

    Note: By default, this class uses the standard library json module. To use
    a different JSON implementation, set the `json` attribute of the class or
    instance.
    """

    timestamp_key = 't'
    value_key = 'v'
    json = _json

    def encode(self, state: State) -> bytes:
        """Encode a state to bytes."""
        return self.json.dumps({self.timestamp_key: state.timestamp,
                                self.value_key: state.value},
                               separators=(',', ':')).encode('utf-8')

    def decode(self, raw_state: Optional[bytes]) -> Optional[State]:
        """Decode a state from bytes."""
        if not raw_state:
            return None
        data = self.json.loads(raw_state.decode('utf-8'))
        return State(data[self.timestamp_key], data[self.value_key])


class StructCodec(Codec):
    """Codec for encoding state to packed binary data."""

    def encode(self, state: State) -> bytes:
        """Encode a state to bytes."""
        return struct.pack('<dd', state.timestamp, state.value)

    def decode(self, raw_state: Optional[bytes]) -> Optional[State]:
        """Decode a state from bytes."""
        if not raw_state:
            return None
        return State(*struct.unpack('<dd', raw_state))


def get_codec(name: str) -> Codec:
    """
    Get codec by name.

    :param name: Codec name
    :return: Codec object
    :throws KeyError: If the given codec name is not supported.
    """
    if name == 'json':
        return JsonCodec()
    elif name == 'struct':
        return StructCodec()
    else:
        raise KeyError(name)
