import asyncio
from typing import Any, Optional

from ..common import override
from ..defaults import STREAM_TCP_BUFSIZE
from .base import Connector, Stream, WrapAcceptor


class NULLStream(Stream):

    @override(Stream)
    def write_primitive(self, buf: bytes):
        pass

    @override(Stream)
    async def read_primitive(self) -> bytes:
        return b''


class NULLConnector(Connector):

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        return NULLStream()


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


class TCPConnector(Connector):
    addr: tuple[str, int]
    tcp_extra_kwargs: dict[str, Any]

    def __init__(self,
                 addr: tuple[str, int],
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        reader, writer = await asyncio.open_connection(
            self.addr[0],
            self.addr[1],
            **self.tcp_extra_kwargs,
        )
        stream = TCPStream(reader, writer)
        async with stream.cm(exc_only=True):
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream


class TCPAcceptor(WrapAcceptor):

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, **kwargs):
        stream = TCPStream(reader=reader, writer=writer)
        super().__init__(stream=stream, **kwargs)
