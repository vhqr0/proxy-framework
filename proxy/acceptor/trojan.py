import socket
import struct
from struct import Struct

from ..common import override
from ..stream import ProtocolError, Stream
from .auto import Socks5Atype
from .base import ProxyAcceptor

IPv4Struct = Struct('!BB4sH')
IPv6Struct = Struct('!BB16sH')


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
            # FIXME: \x13\x10(\r\n) may be part of ipv4/ipv6 addr
            buf = await stream.readuntil(b'\r\n', strip=True)
            atype = Socks5Atype(buf[1])
            if atype == Socks5Atype.Domain:
                alen = buf[2]
                cmd, _, _, addr_bytes, port = struct.unpack(
                    f'!BBB{alen}sH', buf)
                addr = addr_bytes.decode()
            elif atype == Socks5Atype.IPv4:
                cmd, _, addr_bytes, port = IPv4Struct.unpack(buf)
                addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
            elif atype == Socks5Atype.IPv6:
                cmd, _, addr_bytes, port = IPv6Struct.unpack(buf)
                addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            else:
                raise ProtocolError('trojan', 'atype')
            if cmd != 1:
                raise ProtocolError('trojan', 'cmd')
            self.addr = addr, port
            return stream
