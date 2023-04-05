from ..common import override
from ..stream import Stream
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

        try:
            headers = await stream.readuntil(b'\r\n\r\n', strip=True)
            if not headers.startswith(b'HTTP/1.1 200'):
                raise RuntimeError('invalid http response')
            if len(rest) != 0:
                stream.write(rest)
                await stream.drain()
            return stream
        except Exception as e:
            exc = e

        try:
            stream.close()
            await stream.wait_closed()
        except Exception:
            pass

        raise exc
