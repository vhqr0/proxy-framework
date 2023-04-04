import re
import socket
import struct

from ..common import override
from ..stream import Stream
from .base import ProxyAcceptor


class HTTPAcceptor(ProxyAcceptor):
    HTTP_RES_TEMPLATE = ('{} 200 Connection Established\r\n'
                         'Connection close\r\n\r\n')
    HTTP_REQ_RE = r'^(\w+) [^ ]+ (HTTP/[^ \r\n]+)\r\n'
    HTTP_HOST_RE = r'\r\nHost: ([^ :\[\]\r\n]+|\[[:0-9a-fA-F]+\])(:([0-9]+))?'

    http_req_re = re.compile(HTTP_REQ_RE)
    http_host_re = re.compile(HTTP_HOST_RE)

    ensure_next_layer = True

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()

        try:
            buf = await stream.peek()
            if buf[0] == 5:
                await self.dispatch_socks5(stream)
            else:
                await self.dispatch_http(stream)
            return stream
        except Exception as e:
            exc = e

        try:
            stream.close()
            await stream.wait_closed()
        except Exception:
            pass

        raise exc

    async def dispatch_socks5(self, stream: Stream):
        buf = await stream.read()
        nmeths = buf[1]
        ver, nmeths, meths = struct.unpack(f'!BB{nmeths}s', buf)
        if ver != 5 or 0 not in meths:
            raise RuntimeError('invalid socks5 request')
        stream.write(b'\x05\x00')
        await stream.drain()
        buf = await stream.read()
        if buf[3] == 3:  # domain
            ver, cmd, rsv, _, _, addr_bytes, port = struct.unpack(
                f'!BBBBB{buf[4]}sH', buf)
            addr = addr_bytes.decode()
        elif buf[3] == 1:  # ipv4
            ver, cmd, rsv, _, addr_bytes, port = struct.unpack('!BBBB4sH', buf)
            addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
        elif buf[3] == 4:  # ipv6
            ver, cmd, rsv, _, addr_bytes, port = struct.unpack(
                '!BBBB16sH', buf)
            addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            raise RuntimeError('invalid socks5 header')
        if ver != 5 or cmd != 1 or rsv != 0:
            raise RuntimeError('invalid socks5 header')
        stream.write(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
        await stream.drain()
        self.addr, self.rest = (addr, port), b''

    async def dispatch_http(self, stream: Stream):
        buf = await stream.read()
        headers_bytes, rest = buf.split(b'\r\n\r\n', 1)
        headers = headers_bytes.decode()
        req = self.http_req_re.search(headers)
        host = self.http_host_re.search(headers)
        if req is None or host is None:
            raise RuntimeError('invalid http request')
        meth, ver, addr = req[1], req[2], host[1]
        assert meth is not None and ver is not None and addr is not None
        port = 80 if host[3] is None else int(host[3])
        if addr[0] == '[':
            addr = addr[1:-1]
        if meth == 'CONNECT':
            res = self.HTTP_RES_TEMPLATE.format(ver)
            stream.write(res.encode())
            await stream.drain()
        else:
            headers = '\r\n'.join(header for header in headers.split('\r\n')
                                  if not header.startswith('Proxy-'))
            rest = headers.encode() + b'\r\n\r\n' + rest
        self.addr, self.rest = (addr, port), rest
