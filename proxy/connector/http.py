from ..common import override
from ..stream import ProtocolError, Stream
from .base import ProxyConnector


class HTTPConnector(ProxyConnector):
    ensure_next_layer = True

    REQ_FORMAT = 'CONNECT {} HTTP/1.1\r\nHost: {}\r\n\r\n'

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        addr, port = self.addr
        if addr.find(':') >= 0:
            addr = '[' + addr + ']'
        host = '{}:{}'.format(addr, port)
        req = self.REQ_FORMAT.format(host, host)
        stream = await self.next_layer.connect(rest=req.encode())
        async with stream.cm(exc_only=True):
            headers = await stream.readuntil(b'\r\n\r\n', strip=True)
            if not headers.startswith(b'HTTP/1.1 200'):
                raise ProtocolError('http', 'header', 'status')
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream
