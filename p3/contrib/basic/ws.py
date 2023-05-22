import base64
import random
import re
from enum import IntEnum, unique
from hashlib import sha1
from struct import Struct

from p3.defaults import STREAM_BUFSIZE, WS_OUTBOX_HOST, WS_OUTBOX_PATH
from p3.stream import Acceptor, Connector, Stream
from p3.stream.errors import BufferOverflowError, ProtocolError
from p3.utils.override import override

BBStruct = Struct('!BB')
BBHStruct = Struct('!BBH')
BBQStruct = Struct('!BBQ')


@unique
class WSOpcode(IntEnum):
    Continue = 0
    Text = 1
    Binary = 2
    Close = 8
    Ping = 9
    Pong = 10


class WSStream(Stream):
    mask_payload: bool

    ensure_next_layer = True

    def __init__(self, mask_payload: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.mask_payload = mask_payload

    def ws_write(self, opcode: WSOpcode, buf: bytes, fin: bool = True):
        assert self.next_layer is not None
        flags = int(opcode)
        if fin:
            flags += 0x80
        if self.mask_payload:
            mask = 0x80
            mask_key = random.randbytes(4)
            buf = bytes(c ^ mask_key[i % 4] for i, c in enumerate(buf))
        else:
            mask = 0
            mask_key = b''
        blen = len(buf)
        if blen <= 125:
            header = BBStruct.pack(flags, mask + blen)
        elif blen <= 65535:
            header = BBHStruct.pack(flags, mask + 126, blen)
        else:
            header = BBQStruct.pack(flags, mask + 127, blen)
        buf = header + mask_key + buf
        self.next_layer.write(buf)

    async def ws_read(self) -> tuple[WSOpcode, bytes, bool]:
        assert self.next_layer is not None
        flags, blen = await self.next_layer.read_struct(BBStruct)
        fin, opcode = flags & 0x80, WSOpcode(flags & 0xf)
        mask, blen = blen & 0x80, blen & 0x7f
        if blen == 126:
            blen = await self.next_layer.readH()
        elif blen == 127:
            blen = await self.next_layer.readQ()
        if mask != 0:
            mask_key = await self.next_layer.readexactly(4)
            buf = await self.next_layer.readexactly(blen)
            buf = bytes(c ^ mask_key[i % 4] for i, c in enumerate(buf))
        else:
            buf = await self.next_layer.readexactly(blen)
        return opcode, buf, (fin != 0)

    async def ws_read_data(self) -> tuple[WSOpcode, bytes, bool]:
        while True:
            opcode, buf, fin = await self.ws_read()
            if opcode in (WSOpcode.Continue, WSOpcode.Pong):
                continue
            if opcode == WSOpcode.Ping:
                self.ws_write(WSOpcode.Pong, buf)
                await self.drain()
                continue
            if opcode == WSOpcode.Close:
                return WSOpcode.Close, b'', True
            if opcode in (WSOpcode.Text, WSOpcode.Binary):
                return opcode, buf, fin
            raise ProtocolError('ws', 'frame', 'opcode', opcode.name)

    async def ws_read_msg(self) -> tuple[int, bytes]:
        opcode, buf, fin = await self.ws_read_data()
        while not fin:
            next_opcode, next_buf, fin = await self.ws_read_data()
            if next_opcode != opcode:
                raise ProtocolError('ws', 'frame', 'opcode', opcode.name)
            buf += next_buf
            if len(buf) > STREAM_BUFSIZE:
                raise BufferOverflowError(len(buf))
        return opcode, buf

    @override(Stream)
    def write_primitive(self, buf: bytes):
        self.ws_write(WSOpcode.Binary, buf)

    @override(Stream)
    async def read_primitive(self) -> bytes:
        assert self.next_layer is not None
        buf = await self.next_layer.peek()
        if len(buf) == 0:
            return b''
        _, buf = await self.ws_read_msg()
        return buf


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

    def __init__(self,
                 path: str = WS_OUTBOX_PATH,
                 host: str = WS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.path = path
        self.host = host

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        key = base64.b64encode(random.randbytes(16)).decode()
        req = self.REQ_FORMAT.format(self.path, self.host, key)
        next_stream = await self.next_layer.connect(rest=req.encode())
        async with next_stream.cm(exc_only=True):
            headers = await next_stream.readuntil(b'\r\n\r\n', strip=True)
            if not headers.startswith(b'HTTP/1.1 101'):
                raise ProtocolError('ws', 'header', 'status')
            stream = WSStream(next_layer=next_stream)
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream


class WSAcceptor(Acceptor):
    path: str
    host: str

    WS_RES_FORMAT = ('{} 101 Switching Protocols\r\n'
                     'Upgrade: websocket\r\n'
                     'Connection: Upgrade\r\n'
                     'Sec-WebSocket-Accept: {}\r\n'
                     'Sec-WebSocket-Version: 13\r\n\r\n')
    HTTP_REQ_PATTERN = r'^GET ([^ ]+) (HTTP/[^ \r\n]+)\r\n'
    HTTP_HOST_PATTERN = (r'\r\nHost: ([^ :\[\]\r\n]+|\[[:0-9a-fA-F]+\])'
                         r'(:([0-9]+))?')
    WS_KEY_PATTERN = r'\r\nSec-WebSocket-Key: ([a-zA-Z+/=]*)'
    WS_MAGIC = '258EAFA5-E914-47DA- 95CA-C5AB0DC85B11'

    http_req_re = re.compile(HTTP_REQ_PATTERN)
    http_host_re = re.compile(HTTP_HOST_PATTERN)
    ws_key_re = re.compile(WS_KEY_PATTERN)

    ensure_next_layer = True

    @override(Acceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        next_stream = await self.next_layer.accept()
        async with next_stream.cm(exc_only=True):
            buf = await next_stream.readuntil(b'\r\n\r\n', strip=True)
            headers = buf.decode()
            req_match = self.http_req_re.search(headers)
            host_match = self.http_host_re.search(headers)
            key_match = self.ws_key_re.search(headers)
            if req_match is None or host_match is None or key_match is None:
                raise ProtocolError('ws', 'header')
            path, ver, host, key = \
                req_match[1], req_match[2], host_match[1], key_match[1]
            key_hash = sha1((key + self.WS_MAGIC).encode()).digest()
            accept = base64.b64encode(key_hash).decode()
            res = self.WS_RES_FORMAT.format(ver, accept)
            await next_stream.writedrain(res.encode())
            self.path, self.host = path, host
            return WSStream(mask_payload=False, next_layer=next_stream)
