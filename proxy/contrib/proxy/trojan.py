from struct import Struct

from proxy.common import override
from proxy.stream import ProxyAcceptor, ProxyConnector, Stream
from proxy.stream.errors import ProtocolError
from proxy.stream.structs import HStruct

from .socks5 import Atype, Cmd

BBStruct = Struct('!BB')
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
            _cmd, _atype = await stream.read_struct(BBStruct)
            cmd, atype = Cmd(_cmd), Atype(_atype)
            if cmd != Cmd.Connect:
                raise ProtocolError('trojan', 'header', cmd.name)
            self.addr = await atype.read_addr_from_stream(stream)
            buf = await stream.readexactly(2)
            if buf != b'\r\n':
                raise ProtocolError('trojan', 'header', cmd.name)
            return stream
