from struct import Struct

from ..common import override
from ..stream import Stream
from ..stream.structs import HStruct
from .base import ProxyConnector

BBBStruct = Struct('!BBB')


class TrojanConnector(ProxyConnector):
    auth: bytes

    ensure_next_layer = True

    def __init__(self, auth: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(auth) == 56
        self.auth = auth

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        addr, port = self.addr
        addr_bytes = addr.encode()
        req = self.auth + \
            b'\r\n' + \
            BBBStruct.pack(1, 3, len(addr_bytes)) + \
            addr_bytes + \
            HStruct.pack(port) + \
            b'\r\n' + \
            rest
        return await self.next_layer.connect(rest=req)
