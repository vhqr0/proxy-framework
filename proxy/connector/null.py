from ..common import override
from ..stream import Stream, NULLStream
from .base import Connector


class NULLConnector(Connector):

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        return NULLStream()
