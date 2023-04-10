import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Optional

from typing_extensions import Self

from ..common import Loggable, MultiLayer
from ..defaults import STREAM_BUFSIZE


class StreamError(Exception):
    pass


class ProtocolError(RuntimeError, StreamError):
    breadcrumb: list[str]
    protocol: str
    part: str

    def __init__(self, *breadcrumb: str):
        super().__init__('error from protocol {}'.format('/'.join(breadcrumb)))
        self.breadcrumb = list(breadcrumb)


class BufferOverflowError(asyncio.LimitOverrunError, StreamError):

    def __init__(self, consumed: int = 0):
        super().__init__(message='buffer overflow', consumed=consumed)


class IncompleteReadError(asyncio.IncompleteReadError, StreamError):
    pass


class Stream(MultiLayer['Stream'], Loggable, ABC):
    to_read: bytes

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.to_read = b''

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
        self.to_read = buf + self.to_read

    def pop(self) -> bytes:
        buf, self.to_read = self.to_read, b''
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
        if len(self.to_read) == 0:
            self.to_read = await self.read_primitive()
        return self.to_read

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

    async def readuntil(self,
                        separator: bytes = b'\n',
                        strip: bool = False) -> bytes:
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
