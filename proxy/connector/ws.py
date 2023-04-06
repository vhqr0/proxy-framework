import base64
import random

from ..common import override
from ..stream import Stream, WSStream
from .base import Connector


class WSConnector(Connector):
    path: str
    host: str

    REQ_FORMAT = ('GET {} HTTP/1.1\r\n'
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
        req = self.REQ_FORMAT.format(self.path, self.host, key)
        next_stream = await self.next_layer.connect(rest=req.encode())
        async with next_stream.cm(exc_only=True):
            headers = await next_stream.readuntil(b'\r\n\r\n', strip=True)
            if not headers.startswith(b'HTTP/1.1 101'):
                raise RuntimeError('invalid ws response')
            stream = WSStream(next_layer=next_stream)
            if len(rest) != 0:
                await stream.writeall(rest)
            return stream
