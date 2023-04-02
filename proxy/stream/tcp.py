import asyncio

from typing import Optional

from ..common import override
from .base import Stream


class TCPStream(Stream):
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, **kwargs):
        super().__init__(**kwargs)
        self.reader = reader
        self.writer = writer

    @override(Stream)
    def close(self):
        exc: Optional[Exception] = None
        try:
            self.writer.close()
        except Exception as e:
            exc = e
        try:
            super().close()
        except Exception as e:
            if exc is None:
                exc = e
        if exc is not None:
            raise exc

    @override(Stream)
    async def wait_closed(self):
        exc: Optional[Exception] = None
        try:
            await self.writer.wait_closed()
        except Exception as e:
            exc = e
        try:
            await super().wait_closed()
        except Exception as e:
            if exc is None:
                exc = e
        if exc is not None:
            raise exc

    @override(Stream)
    def write_eof(self):
        if self.writer.can_write_eof():
            self.writer.write_eof()
        super().write_eof()

    @override(Stream)
    def write(self, buf: bytes):
        self.writer.write(buf)

    @override(Stream)
    async def drain(self):
        await self.writer.drain()

    @override(Stream)
    async def read(self) -> bytes:
        buf = self.pop()
        if len(buf) != 0:
            return buf
        return await self.reader.read(4096)
