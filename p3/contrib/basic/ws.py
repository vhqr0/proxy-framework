"""Websocket protocol implementation.

See RFC 6455 for more detials.

Links:
  https://www.rfc-editor.org/rfc/rfc6455
"""
import base64
import random
from dataclasses import dataclass
from enum import IntEnum, unique
from hashlib import sha1
from http import HTTPStatus
from struct import Struct
from typing import Optional

from typing_extensions import Self

from p3.contrib.basic.http import HTTPRequest, HTTPResponse
from p3.defaults import STREAM_BUFSIZE, WS_OUTBOX_HOST, WS_OUTBOX_PATH
from p3.stream import Acceptor, Connector, Stream
from p3.stream.errors import BufferOverflowError, ProtocolError
from p3.utils.override import override

BBStruct = Struct('!BB')
BBHStruct = Struct('!BBH')
BBQStruct = Struct('!BBQ')


@unique
class WSOpcode(IntEnum):
    """
    *  %x0 denotes a continuation frame
    *  %x1 denotes a text frame
    *  %x2 denotes a binary frame
    *  %x3-7 are reserved for further non-control frames
    *  %x8 denotes a connection close
    *  %x9 denotes a ping
    *  %xA denotes a pong
    *  %xB-F are reserved for further control frames
    """
    Continuation = 0
    Text = 1
    Binary = 2
    ConnectionClose = 8
    Ping = 9
    Pong = 10


@dataclass
class WSFrame:
    """
     0                   1                   2                   3
     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
    +-+-+-+-+-------+-+-------------+-------------------------------+
    |F|R|R|R| opcode|M| Payload len |    Extended payload length    |
    |I|S|S|S|  (4)  |A|     (7)     |             (16/64)           |
    |N|V|V|V|       |S|             |   (if payload len==126/127)   |
    | |1|2|3|       |K|             |                               |
    +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
    |     Extended payload length continued, if payload len == 127  |
    + - - - - - - - - - - - - - - - +-------------------------------+
    |                               |Masking-key, if MASK set to 1  |
    +-------------------------------+-------------------------------+
    | Masking-key (continued)       |          Payload Data         |
    +-------------------------------- - - - - - - - - - - - - - - - +
    :                     Payload Data continued ...                :
    + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
    |                     Payload Data continued ...                |
    +---------------------------------------------------------------+
    """
    fin: bool
    mask: bool
    key: Optional[bytes]
    opcode: WSOpcode
    payload: bytes

    def do_mask(self):
        if self.mask:
            return
        self.mask = True
        self._mask_payload()

    def do_unmask(self):
        if not self.mask:
            return
        self.mask = False
        self._mask_payload()

    def _mask_payload(self):
        if self.key is None:
            self.key = random.randbytes(4)
        self.payload = bytes(c ^ self.key[i % 4]
                             for i, c in enumerate(self.payload))

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        _opcode, plen = await stream.read_struct(BBStruct)
        if _opcode & 0x70 != 0:
            raise ProtocolError('ws', 'frame', 'rsv')
        fin, opcode = bool(_opcode & 0x80), WSOpcode(_opcode & 0xf)
        mask, plen = bool(plen & 0x80), plen & 0x7f
        if plen == 126:
            plen = await stream.readH()
        elif plen == 127:
            plen = await stream.readQ()
        key: Optional[bytes] = None
        if mask:
            key = await stream.readexactly(4)
        payload = await stream.readexactly(plen)
        return cls(
            fin=fin,
            mask=mask,
            key=key,
            opcode=opcode,
            payload=payload,
        )

    def pack(self) -> bytes:
        opcode = int(self.opcode)
        if self.fin:
            opcode += 0x80
        plen = len(self.payload)
        mask = 0x80 if self.mask else 0
        if plen <= 125:
            header = BBStruct.pack(opcode, mask + plen)
        elif plen <= 65535:
            header = BBHStruct.pack(opcode, mask + 126, plen)
        else:
            header = BBQStruct.pack(opcode, mask + 127, plen)
        if self.mask:
            assert self.key is not None
            header += self.key
        return header + self.payload


class WSStream(Stream):
    do_mask_payload: bool
    ping_received: bool
    pong_received: bool

    ensure_next_layer = True

    def __init__(self, do_mask_payload: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.do_mask_payload = do_mask_payload
        self.ping_received = False
        self.pong_received = False

    async def ws_read_data_frame(self) -> WSFrame:
        assert self.next_layer is not None
        while True:
            frame = await WSFrame.read_from_stream(self.next_layer)
            if frame.opcode is WSOpcode.Continuation:
                continue
            if frame.opcode is WSOpcode.Pong:
                self.pong_received = True
                continue
            if frame.opcode is WSOpcode.Ping:
                self.ping_received = True
                frame.opcode = WSOpcode.Pong
                if self.do_mask_payload:
                    frame.do_mask()
                self.next_layer.write(frame.pack())
                continue
            if frame.opcode in (WSOpcode.Text, WSOpcode.Binary,
                                WSOpcode.ConnectionClose):
                return frame
            raise ProtocolError('ws', 'frame', 'opcode', frame.opcode.name)

    async def ws_read_data(self) -> tuple[WSOpcode, bytes, bool]:
        frame = await self.ws_read_data_frame()
        frame.do_unmask()
        return frame.opcode, frame.payload, frame.fin

    async def ws_read_msg(self) -> tuple[WSOpcode, bytes]:
        opcode, buf, fin = await self.ws_read_data()
        while not fin:
            next_opcode, next_buf, fin = await self.ws_read_data()
            if next_opcode != opcode:
                raise ProtocolError('ws', 'frame', 'fin')
            buf += next_buf
            if len(buf) > STREAM_BUFSIZE:
                raise BufferOverflowError(len(buf))
        return opcode, buf

    @override(Stream)
    def write_primitive(self, buf: bytes):
        assert self.next_layer is not None
        frame = WSFrame(
            fin=False,
            mask=False,
            key=None,
            opcode=WSOpcode.Binary,
            payload=buf,
        )
        if self.do_mask_payload:
            frame.do_mask()
        self.next_layer.write(frame.pack())

    @override(Stream)
    async def read_primitive(self) -> bytes:
        assert self.next_layer is not None
        buf = await self.next_layer.peek()
        if len(buf) == 0:
            return b''
        opcode, buf = await self.ws_read_msg()
        if opcode is WSOpcode.ConnectionClose:
            return b''
        return buf


class WSConnector(Connector):
    host: str
    path: str
    extra_headers: Optional[dict[str, str]]

    ensure_next_layer = True

    def __init__(
        self,
        host: str = WS_OUTBOX_HOST,
        path: str = WS_OUTBOX_PATH,
        extra_headers: Optional[dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.host = host
        self.path = path
        self.extra_headers = extra_headers

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        key = base64.b64encode(random.randbytes(16)).decode()
        headers = {
            'Host': self.host,
            'Upgrade': 'websocket',
            'Connection': 'Upgrade',
            'Sec-WebSocket-Key': key,
            'Sec-WebSocket-Version': '13',
        }
        req = HTTPRequest(method='GET', path=self.path, headers=headers)
        if self.extra_headers is not None:
            req.add_headers(self.extra_headers)
        next_stream = await self.next_layer.connect(rest=req.pack())
        async with next_stream.cm(exc_only=True):
            resp = await HTTPResponse.read_from_stream(next_stream)
            status = resp.statuscode
            if status != HTTPStatus.SWITCHING_PROTOCOLS:
                raise ProtocolError('ws', 'status', status.name)
            stream = WSStream(next_layer=next_stream)
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream


class WSAcceptor(Acceptor):
    req: HTTPRequest

    WS_MAGIC = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

    ensure_next_layer = True

    @override(Acceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        next_stream = await self.next_layer.accept()
        async with next_stream.cm(exc_only=True):
            req = await HTTPRequest.read_from_stream(next_stream)
            if req.version.upper() != 'HTTP/1.1':
                raise ProtocolError('http', 'version', req.version)
            if req.method.upper() != 'GET':
                raise ProtocolError('ws', 'method', req.method)
            if req.headers['Connection'] != 'Upgrade' or \
               req.headers['Upgrade'] != 'websocket':
                raise ProtocolError('ws', 'upgrade')
            version = req.headers['Sec-WebSocket-Version']
            key = req.headers['Sec-WebSocket-Key']
            if version != '13':
                raise ProtocolError('ws', 'version', version)
            key_hash = sha1((key + self.WS_MAGIC).encode()).digest()
            accept = base64.b64encode(key_hash).decode()
            headers = {
                'Upgrade': 'websocket',
                'Connection': 'Upgrade',
                'Sec-WebSocket-Accept': accept,
                'Sec-WebSocket-Version': '13',
            }
            resp = HTTPResponse(
                status=HTTPStatus.SWITCHING_PROTOCOLS,
                headers=headers,
            )
            await next_stream.writedrain(resp.pack())
            self.req = req
            return WSStream(next_layer=next_stream)
