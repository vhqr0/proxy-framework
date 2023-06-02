import asyncio
from typing import Any, Optional

from p3.defaults import STREAM_TCP_BUFSIZE
from p3.iobox import Outbox
from p3.stream import Connector, ProxyRequest, Stream, StreamWrappedAcceptor
from p3.utils.override import override


class TCPStream(Stream):
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        **kwargs,
    ):
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

    def __init__(
        self,
        addr: tuple[str, int],
        tcp_extra_kwargs: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if tcp_extra_kwargs is None:
            tcp_extra_kwargs = dict()
        self.addr = addr
        self.tcp_extra_kwargs = tcp_extra_kwargs

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


class TCPAcceptor(StreamWrappedAcceptor):

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        **kwargs,
    ):
        stream = TCPStream(reader=reader, writer=writer)
        super().__init__(stream=stream, **kwargs)


class TCPOutbox(Outbox):
    scheme = 'tcp'
    ping_skip = True

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=req.addr,
        )
        return await connector.connect(rest=req.rest)


class DirectOutbox(TCPOutbox):
    scheme = 'direct'
