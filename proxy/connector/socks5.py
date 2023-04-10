from struct import Struct

from ..acceptor.auto import Atype
from ..common import override
from ..stream import Stream
from ..stream.errors import ProtocolError
from ..stream.structs import HStruct
from .base import ProxyConnector

BBBBStruct = Struct('!BBBB')
BBBBBStruct = Struct('!BBBBB')


class Socks5Connector(ProxyConnector):
    ensure_next_layer = True

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.connect(b'\x05\x01\x00')
        async with stream.cm(exc_only=True):
            buf = await stream.readexactly(2)
            if buf != '\x05\x00':
                raise ProtocolError('socks5', 'auth')
            addr, port = self.addr
            addr_bytes = addr.encode()
            req = BBBBBStruct(5, 1, 0, 3, len(addr_bytes)) + \
                addr_bytes + \
                HStruct.pack(port)
            await stream.writedrain(req)
            ver, rep, rsv, atype = await stream.read_struct(BBBBStruct)
            if ver != 5 or rep != 0 or rsv != 0:
                raise ProtocolError('socks5', 'header')
            await Atype(atype).read_addr_from_stream()
            return stream
