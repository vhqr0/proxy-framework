from ..common import override
from ..stream import Stream
from ..connector import TCPConnector, HTTPConnector
from ..inbox import Request
from .base import Outbox


class HTTPOutbox(Outbox):
    scheme = 'http'

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(addr=self.url.addr)
        connector = HTTPConnector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)
