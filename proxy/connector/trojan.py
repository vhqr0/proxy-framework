import struct

from ..common import override
from ..stream import Stream
from .base import ProxyConnector


class TrojanConnector(ProxyConnector):
    pwd: bytes

    ensure_next_layer = True

    def __init__(self, pwd: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(pwd) == 56
        self.pwd = pwd

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        addr, port = self.addr
        addr_bytes = addr.encode()
        alen = len(addr_bytes)
        req = struct.pack(f'!BBB{alen}sH', 1, 3, alen, addr_bytes, port)
        req = self.pwd + b'\r\n' + req + b'\r\n' + rest
        return await self.next_layer.connect(req)
