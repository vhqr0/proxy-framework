import asyncio
import random
import struct
from enum import IntEnum, unique

from ..common import override
from ..defaults import STREAM_BUFSIZE
from .base import ProtocolError, Stream


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
            header = struct.pack('!BB', flags, mask + blen)
        elif blen <= 65535:
            header = struct.pack('!BBH', flags, mask + 126, blen)
        else:
            header = struct.pack('!BBQ', flags, mask + 127, blen)
        buf = header + mask_key + buf
        self.next_layer.write(buf)

    async def ws_read(self) -> tuple[WSOpcode, bytes, bool]:
        assert self.next_layer is not None
        buf = await self.next_layer.readexactly(2)
        flags, blen = struct.unpack('!BB', buf)
        fin, opcode = flags & 0x80, WSOpcode(flags & 0xf)
        mask, blen = blen & 0x80, blen & 0x7f
        if blen == 126:
            buf = await self.next_layer.readexactly(2)
            blen, = struct.unpack('!H', buf)
        elif blen == 127:
            buf = await self.next_layer.readexactly(8)
            blen, = struct.unpack('!Q', buf)
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
            raise ProtocolError('ws', 'opcode')

    async def ws_read_msg(self) -> tuple[int, bytes]:
        opcode, buf, fin = await self.ws_read_data()
        while not fin:
            next_opcode, next_buf, fin = await self.ws_read_data()
            if next_opcode != opcode:
                raise ProtocolError('ws', 'opcode')
            buf += next_buf
            if len(buf) > STREAM_BUFSIZE:
                raise asyncio.LimitOverrunError(
                    message='read over buffer size',
                    consumed=len(buf),
                )
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
