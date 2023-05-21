import re

from proxy.common.tcp import TCPConnector
from proxy.iobox import Outbox, TLSCtxOutbox
from proxy.stream import ProxyAcceptor, ProxyConnector, ProxyRequest, Stream
from proxy.stream.errors import ProtocolError
from proxy.utils.override import override


class HTTPConnector(ProxyConnector):
    HTTP_REQ_FORMAT = 'CONNECT {} HTTP/1.1\r\nHost: {}\r\n\r\n'

    ensure_next_layer = True

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        addr, port = self.addr
        if addr.find(':') >= 0:
            addr = '[' + addr + ']'
        host = '{}:{}'.format(addr, port)
        req = self.HTTP_REQ_FORMAT.format(host, host)
        stream = await self.next_layer.connect(rest=req.encode())
        async with stream.cm(exc_only=True):
            headers = await stream.readuntil(b'\r\n\r\n', strip=True)
            if not headers.startswith(b'HTTP/1.1 200'):
                raise ProtocolError('http', 'header', 'status')
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream


class HTTPAcceptor(ProxyAcceptor):
    HTTP_RES_FORMAT = ('{} 200 Connection Established\r\n'
                       'Connection: close\r\n\r\n')
    HTTP_REQ_PATTERN = r'^(\w+) [^ ]+ (HTTP/[^ \r\n]+)\r\n'
    HTTP_HOST_PATTERN = (r'\r\nHost: ([^ :\[\]\r\n]+|\[[:0-9a-fA-F]+\])'
                         r'(:([0-9]+))?')

    http_req_re = re.compile(HTTP_REQ_PATTERN)
    http_host_re = re.compile(HTTP_HOST_PATTERN)

    ensure_next_layer = True

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            await self.dispatch_http(stream)
            return stream

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


class HTTPOutbox(Outbox):
    scheme = 'http'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = HTTPConnector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)


class HTTPSOutbox(HTTPOutbox, TLSCtxOutbox):
    scheme = 'https'
