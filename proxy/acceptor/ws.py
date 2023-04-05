import base64
import re
from hashlib import sha1

from ..common import override
from ..stream import Stream, WSStream
from .base import Acceptor


class WSAcceptor(Acceptor):
    path: str
    host: str

    WS_RES_FORMAT = ('{} 101 Switching Protocols\r\n'
                     'Upgrade: websocket\r\n'
                     'Connection: Upgrade\r\n'
                     'Sec-WebSocket-Accept: {}\r\n'
                     'Sec-WebSocket-Version: 13\r\n\r\n')
    HTTP_REQ_RE = r'^GET ([^ ]+) (HTTP/[^ \r\n]+)\r\n'
    HTTP_HOST_RE = r'\r\nHost: ([^ :\[\]\r\n]+|\[[:0-9a-fA-F]+\])(:([0-9]+))?'
    WS_KEY_RE = r'\r\nSec-WebSocket-Key: ([a-zA-Z+/=]*)'
    WS_MAGIC = '258EAFA5-E914-47DA- 95CA-C5AB0DC85B11'

    http_req_re = re.compile(HTTP_REQ_RE)
    http_host_re = re.compile(HTTP_HOST_RE)
    ws_key_re = re.compile(WS_KEY_RE)

    ensure_next_layer = True

    @override(Acceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        next_stream = await self.next_layer.accept()

        try:
            buf = await next_stream.read()
            headers_bytes, content = buf.split(b'\r\n\r\n', 1)
            next_stream.push(content)
            headers = headers_bytes.decode()
            req_match = self.http_req_re.search(headers)
            host_match = self.http_host_re.search(headers)
            key_match = self.ws_key_re.search(headers)
            if req_match is None or host_match is None or key_match is None:
                raise RuntimeError('invalid http request')
            path, ver = req_match[1], req_match[2]
            host, key = host_match[1], key_match[1]
            self.path = path
            self.host = host
            key_hash = sha1((key + self.WS_MAGIC).encode()).digest()
            accept = base64.b64encode(key_hash).decode()
            res = self.WS_RES_FORMAT.format(ver, accept)
            next_stream.write(res.encode())
            await next_stream.drain()
            stream = WSStream(mask_payload=False, next_layer=next_stream)
            return stream
        except Exception as e:
            exc = e

        try:
            next_stream.close()
            await stream.wait_closed()
        except Exception:
            pass

        raise exc
