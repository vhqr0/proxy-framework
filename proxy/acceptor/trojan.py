from struct import Struct

from ..common import override
from ..stream import Stream
from ..stream.errors import ProtocolError
from .auto import Atype
from .base import ProxyAcceptor

BBStruct = Struct('!BB')


class TrojanAcceptor(ProxyAcceptor):
    auth: bytes

    ensure_next_layer = True

    def __init__(self, auth: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(auth) == 56
        self.auth = auth

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            buf = await stream.readuntil(b'\r\n', strip=True)
            if buf != self.auth:
                raise ProtocolError('trojan', 'auth')
            cmd, atype = await stream.read_struct(BBStruct)
            if cmd != 1:
                raise ProtocolError('trojan', 'header')
            self.addr = await Atype(atype).read(stream)
            buf = await stream.readexactly(2)
            if buf != b'\r\n':
                raise ProtocolError('trojan', 'header')
            return stream
