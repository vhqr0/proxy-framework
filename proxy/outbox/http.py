from ..common import override
from ..stream import Stream
from ..connector import TCPConnector, HTTPConnector
from ..inbox import Request
from .base import PeerOutbox


class HTTPOutbox(PeerOutbox):
    scheme = 'http'

    @override(PeerOutbox)
    async def connect(self, req: Request) -> Stream:
        addr, port = req.addr
        if addr.find(':') >= 0:
            addr = '[' + addr + ']'
        host = '{}:{}'.format(addr, port)
        next_connector = TCPConnector(addr=self.addr)
        connector = HTTPConnector(host=host, next_layer=next_connector)
        return await connector.connect(rest=req.rest)
