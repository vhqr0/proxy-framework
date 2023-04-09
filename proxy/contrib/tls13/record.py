import asyncio
import struct
from dataclasses import dataclass

from typing_extensions import Self

from proxy.stream import ProtocolError, Stream

from .consts import (AlertDescription, AlertLevel, ChangeCipherSpecType,
                     ContentType, HandshakeType, Version)
from .defaults import STREAM_TLS13_BUFSIZE


@dataclass
class Record:
    btype: ContentType
    ver: Version
    buf: bytes

    def __bytes__(self) -> bytes:
        header = struct.pack('!BHH', self.btype, self.ver, len(self.buf))
        return header + self.buf

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        buf = await stream.readexactly(5)
        btype, ver, blen = struct.unpack('!BHH', buf)
        if blen > STREAM_TLS13_BUFSIZE:
            raise asyncio.LimitOverrunError(
                message='read over buffer size',
                consumed=0,
            )
        buf = await stream.readexactly(blen)
        return cls(btype=btype, ver=Version(ver), buf=buf)


@dataclass
class ChangeCipherSpec:
    ctype: ChangeCipherSpecType

    def __bytes__(self) -> bytes:
        return struct.pack('!B', self.ctype)

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        ctype, = struct.unpack('!B', buf)
        return cls(ctype=ChangeCipherSpecType(ctype))


@dataclass
class Alert:
    level: AlertLevel
    desc: AlertDescription

    def __bytes__(self) -> bytes:
        return struct.pack('!BB', self.level, self.desc)

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        level, desc = struct.unpack('!BB', buf)
        return cls(level=AlertLevel(level), desc=AlertDescription(desc))


@dataclass
class Handshake:
    btype: HandshakeType
    buf: bytes

    def __bytes__(self) -> bytes:
        return struct.pack('!I', (self.btype << 24) + len(self.buf)) + self.buf

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        blen, = struct.unpack_from('!I', buffer=buf, offset=0)
        btype, blen = (blen & 0xff000000) >> 24, blen & 0xfff
        if len(buf) != blen + 4:
            raise ProtocolError('tls', 'handshake')
        return cls(btype=HandshakeType(btype), buf=buf[4:])
