import socket
import struct

from ..common import override
from ..stream import ProtocolError, Stream
from .base import ProxyAcceptor


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
            buf = await stream.readuntil(b'\r\n', strip=True)
            if buf[1] == 3:  # domain
                alen = buf[2]
                cmd, _, _, addr_bytes, port = struct.unpack(
                    f'!BBB{alen}sH', buf)
                addr = addr_bytes.decode()
            elif buf[1] == 1:  # ipv4
                cmd, _, addr_bytes, port = struct.unpack('!BB4sH', buf)
                addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
            elif buf[1] == 4:  # ipv6
                cmd, _, addr_bytes, port = struct.unpack('!BB16sH', buf)
                addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
            else:
                raise ProtocolError('trojan', 'header')
            if cmd != 1:
                raise ProtocolError('trojan', 'header')
            self.addr = addr, port
            return stream
