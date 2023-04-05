import asyncio
from typing import Optional

from ..common import override
from ..defaults import STREAM_TCP_BUFSIZE
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
        self.writer.close()

    @override(Stream)
    async def wait_closed(self):
        await self.writer.wait_closed()

    @override(Stream)
    def write_primitive(self, buf: bytes):
        self.writer.write(buf)

    @override(Stream)
    async def drain(self):
        await self.writer.drain()

    @override(Stream)
    async def read_primitive(self) -> bytes:
        return await self.reader.read(STREAM_TCP_BUFSIZE)
