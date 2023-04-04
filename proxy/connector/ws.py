import random
import base64

from ..common import override
from ..stream import Stream, WSStream
from .base import Connector


class WSConnector(Connector):
    path: str
    host: str

    REQ_TEMPLATE = ('GET {} HTTP/1.1\r\n'
                    'Host: {}\r\n'
                    'Upgrade: websocket\r\n'
                    'Connection: Upgrade\r\n'
                    'Sec-WebSocket-Key: {}\r\n'
                    'Sec-WebSocket-Version: 13\r\n\r\n')

    ensure_next_layer = True

    def __init__(self, path: str = '/', host: str = 'localhost', **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.host = host

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        key = base64.b64decode(random.randbytes(16)).decode()
        req = self.REQ_TEMPLATE.format(self.path, self.host, key)
        next_stream = await self.next_layer.connect(rest=req.encode())

        try:
            buf = await next_stream.read()
            headers, content = buf.split(b'\r\n\r\n', 1)
            next_stream.push(content)
            if not headers.startswith(b'HTTP/1.1 101'):
                raise RuntimeError('invalid ws response')
            stream = WSStream(next_layer=next_stream)
            if len(rest) != 0:
                stream.write(rest)
                await stream.drain()
            return stream
        except Exception as e:
            exc = e

        try:
            next_stream.close()
            await next_stream.wait_closed()
        except Exception:
            pass

        raise exc
