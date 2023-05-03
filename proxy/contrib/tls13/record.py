from dataclasses import dataclass
from struct import Struct

from typing_extensions import Self

from proxy.stream import Stream
from proxy.stream.errors import BufferOverflowError, ProtocolError
from proxy.stream.null import NULLStream
from proxy.stream.structs import BStruct, IStruct

from .consts import (AlertDescription, AlertLevel, ChangeCipherSpecType,
                     ContentType, HandshakeType, Version)
from .defaults import STREAM_TLS13_BUFSIZE

BBStruct = Struct('!BB')
BHHStruct = Struct('!BHH')


@dataclass
class Record:
    btype: ContentType
    ver: Version
    buf: bytes

    def __bytes__(self) -> bytes:
        header = BHHStruct.pack(self.btype, self.ver, len(self.buf))
        return header + self.buf

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        btype, ver, blen = await stream.read_struct(BHHStruct)
        if blen > STREAM_TLS13_BUFSIZE:
            raise BufferOverflowError(blen)
        buf = await stream.readexactly(blen)
        return cls(btype=btype, ver=Version(ver), buf=buf)


@dataclass
class ChangeCipherSpec:
    ctype: ChangeCipherSpecType

    def __bytes__(self) -> bytes:
        return BStruct.pack(self.ctype)

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        ctype, = BStruct.unpack(buf)
        return cls(ctype=ChangeCipherSpecType(ctype))


@dataclass
class Alert:
    level: AlertLevel
    desc: AlertDescription

    def __bytes__(self) -> bytes:
        return BBStruct.pack(self.level, self.desc)

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        level, desc = BBStruct.unpack(buf)
        return cls(level=AlertLevel(level), desc=AlertDescription(desc))


@dataclass
class Handshake:
    btype: HandshakeType
    buf: bytes

    def __bytes__(self) -> bytes:
        return IStruct.pack((self.btype << 24) + len(self.buf)) + self.buf

    @classmethod
    def from_bytes(cls, buf: bytes) -> Self:
        stream = NULLStream(buf=buf)
        blen = stream.popI()
        btype, blen = (blen & 0xff000000) >> 24, blen & 0xfff
        buf = stream.popexactly(blen)
        if len(stream.to_read) != 0:
            raise ProtocolError('tls', 'frame', 'remain')
        return cls(btype=HandshakeType(btype), buf=buf[4:])
