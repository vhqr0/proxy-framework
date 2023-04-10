import random
from enum import IntEnum, unique
from struct import Struct

from ..common import override
from ..defaults import STREAM_BUFSIZE
from .base import Stream
from .errors import BufferOverflowError, ProtocolError

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
            raise ProtocolError('ws', 'frame', 'opcode')

    async def ws_read_msg(self) -> tuple[int, bytes]:
        opcode, buf, fin = await self.ws_read_data()
        while not fin:
            next_opcode, next_buf, fin = await self.ws_read_data()
            if next_opcode != opcode:
                raise ProtocolError('ws', 'frame', 'opcode')
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
