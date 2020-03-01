"""Classes for encoding rate limiter state as binary data."""

import json as _json
import struct
from abc import ABC, abstractmethod
from typing import Optional, Union

from redbucket.data import State

__all__ = ('DEFAULT_CODEC', 'Codec', 'JsonCodec', 'LuaCodec', 'StructCodec',
           'get_codec')

DEFAULT_CODEC = 'struct'


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


class LuaCodec(ABC):
    """Abstract base class for Lua script codecs."""

    @abstractmethod
    def lua_encode(self) -> str:
        """
        Return Lua code for encoding state.

        This code will be used as the body of a Lua function that accepts two
        arguments `(timestamp, value)` and returns the encoded state.
        """
        ...

    @abstractmethod
    def lua_decode(self) -> str:
        """
        Return Lua code for a function for decoding state.

        This code will be used as the body of a Lua function that accepts an
        argument `(raw_state)` and returns two values, timestamp and value.
        """
        ...


class JsonCodec(Codec, LuaCodec):
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

    def lua_encode(self):
        """Return Lua code for encoding state."""
        return ('return cjson.encode({'
                f'["{lua_escape(self.timestamp_key)}"]=timestamp, '
                f'["{lua_escape(self.value_key)}"]=value'
                '})')

    def lua_decode(self):
        """Return Lua code for decoding state."""
        return ('local decoded = cjson.decode(raw_state)\n'
                f'return decoded["{lua_escape(self.timestamp_key)}"], '
                f'decoded["{lua_escape(self.value_key)}"]')


class StructCodec(Codec, LuaCodec):
    """Codec for encoding state to packed binary data."""

    def encode(self, state: State) -> bytes:
        """Encode a state to bytes."""
        return struct.pack('<dd', state.timestamp, state.value)

    def decode(self, raw_state: Optional[bytes]) -> Optional[State]:
        """Decode a state from bytes."""
        if not raw_state:
            return None
        return State(*struct.unpack('<dd', raw_state))

    def lua_encode(self):
        """Return Lua code for encoding state."""
        return 'return struct.pack("<dd", timestamp, value)'

    def lua_decode(self):
        """Return Lua code for decoding state."""
        return 'return struct.unpack("<dd", raw_state)'


def get_codec(name: str) -> Union[JsonCodec, StructCodec]:
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


LUA_ESCAPES = [chr(i) if (0x20 <= i < 0x7f) else f'\\{i:03d}'
               for i in range(256)]
LUA_ESCAPES[0x07] = r'\a'  # bell
LUA_ESCAPES[0x08] = r'\b'  # back space
LUA_ESCAPES[0x0c] = r'\f'  # form feed
LUA_ESCAPES[0x0a] = r'\n'  # newline
LUA_ESCAPES[0x0d] = r'\r'  # carriage return
LUA_ESCAPES[0x09] = r'\t'  # horizontal tab
LUA_ESCAPES[0x0b] = r'\v'  # vertical tab
LUA_ESCAPES[0x5c] = r'\\'  # backslash
LUA_ESCAPES[0x22] = r'\"'  # double quote
LUA_ESCAPES[0x27] = r'\''  # single quote
LUA_ESCAPES[0x5b] = r'\['  # left square bracket
LUA_ESCAPES[0x5d] = r'\]'  # right square bracket


def lua_escape(s: str) -> str:
    """Escape Lua special characters in a string."""
    return ''.join(LUA_ESCAPES[i] for i in s.encode('utf8'))
