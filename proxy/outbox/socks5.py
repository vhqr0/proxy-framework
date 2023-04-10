from ..common import override
from ..connector import Socks5Connector, TCPConnector
from ..request import Request
from ..stream import Stream
from .base import Outbox


class Socks5Outbox(Outbox):
    scheme = 'socks5'

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = Socks5Connector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)


class Socks5hOutbox(Socks5Outbox):
    scheme = 'socks5h'
