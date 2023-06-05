import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from typing_extensions import Self

from p3.defaults import STREAM_BUFSIZE
from p3.stream.errors import BufferOverflowError, IncompleteReadError
from p3.utils.layerable import Layerable
from p3.utils.loggable import Loggable


class Stream(Layerable['Stream'], Loggable, ABC):
    buf: bytes

    def __init__(self, buf: bytes = b'', **kwargs):
        super().__init__(**kwargs)
        self.buf = buf

    @asynccontextmanager
    async def cm(self, exc_only: bool = False) -> AsyncGenerator[Self, None]:
        exc: Optional[BaseException] = None
        try:
            yield self
        except (Exception, asyncio.CancelledError) as e:
            exc = e
        if not exc_only or exc is not None:
            await asyncio.shield(self.ensure_closed())
        if exc is not None:
            raise exc

    def push(self, buf: bytes):
        self.buf = buf + self.buf

    def pop(self) -> bytes:
        buf, self.buf = self.buf, b''
        return buf

    def close(self):
        pass

    async def wait_closed(self):
        pass

    async def ensure_closed(self):
        try:
            self.close()
            await self.wait_closed()
        except Exception:
            pass
        if self.next_layer is not None:
            await self.next_layer.ensure_closed()

    @abstractmethod
    def write_primitive(self, buf: bytes):
        raise NotImplementedError

    def write(self, buf: bytes):
        if len(buf) != 0:
            self.write_primitive(buf)
        else:
            self.logger.debug('write empty bytes')

    async def drain(self):
        if self.next_layer is not None:
            await self.next_layer.drain()

    async def writedrain(self, buf: bytes):
        self.write(buf)
        await self.drain()

    async def write_stream(self, reader: 'Stream'):
        while True:
            buf = await reader.read()
            if len(buf) == 0:
                break
            await self.writedrain(buf)

    @abstractmethod
    async def read_primitive(self) -> bytes:
        raise NotImplementedError

    async def read(self) -> bytes:
        buf = self.pop()
        if len(buf) != 0:
            return buf
        return await self.read_primitive()

    async def peek(self) -> bytes:
        if len(self.buf) == 0:
            self.buf = await self.read_primitive()
        return self.buf

    async def readatmost(self, n: int) -> bytes:
        buf = await self.read()
        if len(buf) > n:
            self.push(buf[n:])
            buf = buf[:n]
        return buf

    async def readatleast(self, n: int) -> bytes:
        if n > STREAM_BUFSIZE:
            raise BufferOverflowError(n)
        buf = b''
        while len(buf) < n:
            next_buf = await self.read()
            if len(next_buf) == 0:
                raise IncompleteReadError(partial=buf, expected=n)
            buf += next_buf
        return buf

    async def readexactly(self, n: int) -> bytes:
        buf = await self.readatleast(n)
        if len(buf) > n:
            self.push(buf[n:])
            buf = buf[:n]
        return buf

    async def readuntil(
        self,
        separator: bytes = b'\n',
        strip: bool = False,
    ) -> bytes:
        buf, sp = b'', [b'']
        while len(sp) == 1:
            next_buf = await self.read()
            if len(next_buf) == 0:
                raise IncompleteReadError(partial=buf, expected=None)
            buf += next_buf
            if len(buf) > STREAM_BUFSIZE:
                raise BufferOverflowError(len(buf))
            sp = buf.split(separator, 1)
        self.push(sp[1])
        buf = sp[0]
        if not strip:
            buf += separator
        return buf
