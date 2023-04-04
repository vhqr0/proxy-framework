from functools import cached_property
from hashlib import sha224

from ..common import override
from ..connector import TCPConnector, TrojanConnector
from ..inbox import Request
from ..stream import Stream
from .base import TLSCtxOutbox


class TrojanOutbox(TLSCtxOutbox):
    scheme = 'trojan'

    @cached_property
    def auth(self) -> bytes:
        return sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxOutbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = TrojanConnector(
            auth=self.auth,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
