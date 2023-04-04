import functools
import hashlib

from ..common import override
from ..stream import Stream
from ..connector import TCPConnector, TrojanConnector
from ..inbox import Request
from .base import TLSCtxOutbox


class TrojanOutbox(TLSCtxOutbox):
    scheme = 'trojan'

    @functools.cached_property
    def pwd_hash(self) -> bytes:
        return hashlib.sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxOutbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = TrojanConnector(
            pwd=self.pwd_hash,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
