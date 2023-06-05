from collections.abc import Callable
from struct import Struct
from typing import Any

from p3.stream.buffer import Buffer
from p3.stream.stream import Stream


class BaseStruct(Struct):

    def pack_varlen(self, buf: bytes) -> bytes:
        return self.pack(len(buf)) + buf

    def unpack_with_types(
        self,
        buf: bytes,
        *ts: Callable[[Any], Any],
    ) -> tuple[Any, ...]:
        vs = self.unpack(buf)
        return tuple(t(v) for t, v in zip(ts, vs))

    async def read_from_stream(self, stream: Stream) -> tuple[Any, ...]:
        buf = await stream.readexactly(self.size)
        return self.unpack(buf)

    async def read_from_stream_with_types(
        self,
        stream: Stream,
        *ts: Callable[[Any], Any],
    ) -> tuple[Any, ...]:
        buf = await stream.readexactly(self.size)
        return self.unpack_with_types(buf, *ts)

    async def read_varlen_from_stream(self, stream: Stream) -> bytes:
        blen, = await self.read_from_stream(stream)
        return await stream.readexactly(blen)

    def pop_from_buffer(self, buffer: Buffer) -> tuple[Any, ...]:
        buf = buffer.pop(self.size)
        return self.unpack(buf)

    def pop_from_buffer_with_types(
        self,
        buffer: Buffer,
        *ts: Callable[[Any], Any],
    ) -> tuple[Any, ...]:
        buf = buffer.pop(self.size)
        return self.unpack_with_types(buf, *ts)

    def pop_varlen_from_buffer(self, buffer: Buffer) -> bytes:
        blen, = self.pop_from_buffer(buffer)
        return buffer.pop(blen)


BStruct = BaseStruct('!B')
HStruct = BaseStruct('!H')
IStruct = BaseStruct('!I')
QStruct = BaseStruct('!Q')
