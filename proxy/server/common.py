from ..common import override
from ..stream import ProxyRequest, Stream
from ..stream.common import NULLConnector, TCPConnector
from .base import Outbox


class NULLOutbox(Outbox):
    scheme = 'null'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        connector = NULLConnector()
        return await connector.connect(rest=req.rest)


class TCPOutbox(Outbox):
    scheme = 'tcp'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=req.addr,
        )
        return await connector.connect(rest=req.rest)


class BlockOutbox(NULLOutbox):
    scheme = 'block'


class DirectOutbox(TCPOutbox):
    scheme = 'direct'
