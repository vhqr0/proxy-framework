from ..common import override
from ..connector import TCPConnector
from ..inbox import Request
from ..stream import Stream
from .base import Outbox


class TCPOutbox(Outbox):
    scheme = 'tcp'

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=req.addr,
        )
        return await connector.connect(rest=req.rest)
