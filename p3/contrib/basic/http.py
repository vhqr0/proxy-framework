"""HTTP protocol implementation.

See RFC 9112 for more detials.

Links:
  https://www.rfc-editor.org/rfc/rfc9112
"""
from http import HTTPStatus
from typing import Optional, Union

from typing_extensions import Self

from p3.common.tcp import TCPConnector
from p3.iobox import Outbox, TLSCtxOutbox
from p3.stream import ProxyAcceptor, ProxyConnector, ProxyRequest, Stream
from p3.stream.enums import BaseEnumMixin, BaseIntEnumProxy, HEnumMixin
from p3.stream.errors import ProtocolError
from p3.utils.override import override


class HTTPEnumMixin(BaseEnumMixin):
    scheme = 'http'


class HTTPStatusProxy(HTTPEnumMixin, HEnumMixin, BaseIntEnumProxy):
    enumType = HTTPStatus


class HTTPHeaders:
    firstline: Optional[str]
    headers: dict[str, str]

    def __init__(
        self,
        firstline: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        if headers is None:
            headers = dict()
        self.firstline = firstline
        self.headers = headers

    def __str__(self) -> str:
        if self.firstline is None:
            self.pack_firstline()
        assert self.firstline is not None
        sp = ['{}: {}'.format(k, v) for k, v in self.headers.items()]
        return self.firstline + '\r\n' + '\r\n'.join(sp) + '\r\n\r\n'

    def __bytes__(self) -> bytes:
        return str(self).encode()

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        buf = await stream.readuntil(b'\r\n\r\n', strip=True)
        sp = buf.decode().split('\r\n')
        firstline = sp[0]
        headers = dict()
        for header in sp[1:]:
            k, v = header.split(':', 1)
            headers[k.strip()] = v.strip()
        return cls(firstline=firstline, headers=headers)

    def pack_firstline(self):
        raise NotImplementedError

    def add_header(self, k: str, v: str):
        self.headers[k] = v

    def add_headers(self, headers: dict[str, str]):
        for k, v in headers.items():
            self.add_header(k, v)


class HTTPRequest(HTTPHeaders):
    method: str
    path: str
    version: str

    def __init__(
        self,
        method: str = 'CONNECT',
        path: str = '/',
        version: str = 'HTTP/1.1',
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.method = method
        self.path = path
        self.version = version

    @property
    def host(self) -> str:
        return self.headers['Host']

    @property
    def addr(self) -> tuple[str, int]:
        host = self.host
        if host[0] == '[':
            sp = host[1:].split(']')
            splen = len(sp)
            if splen == 1:
                return sp[0], 80
            elif splen == 2 and sp[1][0] == ':':
                return sp[0], int(sp[1][1:])
            else:
                raise ProtocolError('http', 'host', host)
        else:
            sp = host.split(':')
            splen = len(sp)
            if splen == 1:
                return sp[0], 80
            elif splen == 2:
                return sp[0], int(sp[1])
            else:
                raise ProtocolError('http', 'host', host)

    @classmethod
    @override(HTTPHeaders)
    async def read_from_stream(cls, stream: Stream) -> Self:
        headers = await HTTPHeaders.read_from_stream(stream)
        assert headers.firstline is not None
        method, path, version = headers.firstline.split()
        return cls(
            method=method,
            path=path,
            version=version,
            firstline=headers.firstline,
            headers=headers.headers,
        )

    @override(HTTPHeaders)
    def pack_firstline(self):
        self.firstline = '{} {} {}'.format(self.method, self.path,
                                           self.version)


class HTTPResponse(HTTPHeaders):
    version: str
    status: Union[str, HTTPStatus]
    reason: str

    def __init__(
        self,
        version: str = 'HTTP/1.1',
        status: Union[str, HTTPStatus] = HTTPStatus.OK,
        reason: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if reason is None:
            if not isinstance(status, HTTPStatus):
                status = HTTPStatus(int(status))
            reason = status.phrase
        self.version = version
        self.status = status
        self.reason = reason

    @property
    def statuscode(self) -> HTTPStatus:
        if isinstance(self.status, HTTPStatus):
            return self.status
        return HTTPStatus(int(self.status))

    @classmethod
    @override(HTTPHeaders)
    async def read_from_stream(cls, stream: Stream) -> Self:
        headers = await HTTPHeaders.read_from_stream(stream)
        assert headers.firstline is not None
        version, status, reason = headers.firstline.split(maxsplit=2)
        return cls(
            version=version,
            status=status,
            reason=reason,
            firstline=headers.firstline,
            headers=headers.headers,
        )

    @override(HTTPHeaders)
    def pack_firstline(self):
        status = self.status
        if isinstance(status, HTTPStatus):
            status = str(status.value)
        self.firstline = '{} {} {}'.format(self.version, status, self.reason)


class HTTPConnector(ProxyConnector):
    extra_headers: Optional[dict[str, str]]

    ensure_next_layer = True

    def __init__(
        self,
        extra_headers: Optional[dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.extra_headers = extra_headers

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        addr, port = self.addr
        if addr.find(':') >= 0:
            addr = '[{}]'.format(addr)
        host = '{}:{}'.format(addr, port)
        req = HTTPRequest(path=host, headers={'Host': host})
        if self.extra_headers is not None:
            req.add_headers(self.extra_headers)
        req_bytes = bytes(req)
        if len(rest) != 0:
            req_bytes += rest
        stream = await self.next_layer.connect(rest=req_bytes)
        async with stream.cm(exc_only=True):
            resp = await HTTPResponse.read_from_stream(stream)
            status = resp.statuscode
            HTTPStatusProxy.OK.ensure(status)
            return stream


class HTTPAcceptor(ProxyAcceptor):
    RESP = bytes(HTTPResponse(headers={'Connection': 'close'}))

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            await self.dispatch_http(stream)
            return stream

    async def dispatch_http(self, stream: Stream):
        req = await HTTPRequest.read_from_stream(stream)
        method, version = req.method, req.version
        if version.upper() != 'HTTP/1.1':
            raise ProtocolError('http', 'version', version)
        if method.upper() == 'CONNECT':
            await stream.writedrain(self.RESP)
        else:
            for k in list(req.headers):
                if k.startswith('Proxy-'):
                    del req.headers[k]
            stream.push(bytes(req))
        self.addr = req.addr


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
