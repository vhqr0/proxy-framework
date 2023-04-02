from ..common import override
from ..stream import Stream
from .base import Connector


class HTTPConnector(Connector):
    host: str

    ensure_next_layer = True

    REQ_TEMPLATE = 'CONNECT {} HTTP/1.1\r\nHost: {}\r\n\r\n'

    def __init__(self, host: str, **kwargs):
        super().__init__(**kwargs)
        self.host = host

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        req = self.REQ_TEMPLATE.format(self.host, self.host)
        stream = await self.next_layer.connect(req.encode())

        try:
            buf = await stream.read()
            headers, content = buf.split(b'\r\n\r\n', 1)
            stream.push(content)
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
