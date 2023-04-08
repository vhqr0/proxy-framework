from ..common import override
from ..connector import HTTPConnector, TCPConnector
from ..request import Request
from ..stream import Stream
from .base import Outbox


class HTTPOutbox(Outbox):
    scheme = 'http'

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = HTTPConnector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)
