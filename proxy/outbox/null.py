from ..common import override
from ..stream import Stream
from ..connector import NULLConnector
from ..inbox import Request
from .base import Outbox


class NULLOutbox(Outbox):
    scheme = 'null'

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        connector = NULLConnector()
        return await connector.connect(rest=req.rest)
