import re
import socket
from enum import IntEnum, unique
from struct import Struct

from ..common import override
from ..stream import Stream
from ..stream.errors import ProtocolError
from .base import ProxyAcceptor

BBStruct = Struct('!BB')
BBBBStruct = Struct('!BBBB')
IPv4Struct = Struct('!4sH')
IPv6Struct = Struct('!16sH')


@unique
class Atype(IntEnum):
    Domain = 3
    IPv4 = 1
    IPv6 = 4

    async def read_addr_from_stream(self, stream: Stream) -> tuple[str, int]:
        if self is self.Domain:
            alen = await stream.readB()
            addr_bytes = await stream.readexactly(alen)
            port = await stream.readH()
            addr = addr_bytes.decode()
        elif self is self.IPv4:
            addr_bytes, port = await stream.read_struct(IPv4Struct)
            addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
        elif self is self.IPv6:
            addr_bytes, port = await stream.read_struct(IPv6Struct)
            addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            raise ProtocolError('socks5', 'atype', self.name)
        return addr, port


class HTTPOrSocks5Acceptor(ProxyAcceptor):
    HTTP_RES_FORMAT = ('{} 200 Connection Established\r\n'
                       'Connection: close\r\n\r\n')
    HTTP_REQ_RE = r'^(\w+) [^ ]+ (HTTP/[^ \r\n]+)\r\n'
    HTTP_HOST_RE = r'\r\nHost: ([^ :\[\]\r\n]+|\[[:0-9a-fA-F]+\])(:([0-9]+))?'

    http_req_re = re.compile(HTTP_REQ_RE)
    http_host_re = re.compile(HTTP_HOST_RE)

    ensure_next_layer = True

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            buf = await stream.peek()
            if len(buf) == 0:
                raise ProtocolError('auto', 'emptycheck')
            if buf[0] == 5:
                await self.dispatch_socks5(stream)
            else:
                await self.dispatch_http(stream)
            return stream

    async def dispatch_socks5(self, stream: Stream):
        ver, nmeths = await stream.read_struct(BBStruct)
        if ver != 5 or nmeths == 0:
            raise ProtocolError('socks5', 'auth')
        meths = await stream.readexactly(nmeths)
        if 0 not in meths:
            raise ProtocolError('socks5', 'auth', 'type')
        await stream.writedrain(b'\x05\x00')
        ver, cmd, rsv, atype = await stream.read_struct(BBBBStruct)
        if ver != 5 or cmd != 1 or rsv != 0:
            raise ProtocolError('socks5', 'header')
        self.addr = await Atype(atype).read_addr_from_stream(stream)
        await stream.writedrain(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')

    async def dispatch_http(self, stream: Stream):
        buf = await stream.readuntil(b'\r\n\r\n', strip=True)
        headers = buf.decode()
        req_match = self.http_req_re.search(headers)
        host_match = self.http_host_re.search(headers)
        if req_match is None or host_match is None:
            raise ProtocolError('http', 'header')
        meth, ver, addr = req_match[1], req_match[2], host_match[1]
        assert meth is not None and ver is not None and addr is not None
        port = 80 if host_match[3] is None else int(host_match[3])
        if addr[0] == '[':
            addr = addr[1:-1]
        if meth == 'CONNECT':
            res = self.HTTP_RES_FORMAT.format(ver)
            await stream.writedrain(res.encode())
        else:
            headers = '\r\n'.join(header for header in headers.split('\r\n')
                                  if not header.startswith('Proxy-'))
            stream.push(headers.encode() + b'\r\n\r\n')
        self.addr = addr, port
