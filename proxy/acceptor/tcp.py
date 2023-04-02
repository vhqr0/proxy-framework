import asyncio

from ..stream import TCPStream
from .wrap import WrapAcceptor


class TCPAcceptor(WrapAcceptor):

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, **kwargs):
        stream = TCPStream(reader=reader, writer=writer)
        super().__init__(stream=stream, **kwargs)
