import random
import struct

from ..common import override
from .base import Stream


class WSStream(Stream):
    mask_payload: bool

    ensure_next_layer = True

    def __init__(self, mask_payload: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.mask_payload = mask_payload

    def write_frame(self, flags: int, buf: bytes):
        assert self.next_layer is not None
        if self.mask_payload:
            m = 0x80
            mask = random.randbytes(4)
            buf = bytes(c ^ mask[i % 4] for i, c in enumerate(buf))
        else:
            m = 0
            mask = b''
        blen = len(buf)
        if blen <= 125:
            header = struct.pack('!BB', flags, m + blen)
        elif blen <= 65535:
            header = struct.pack('!BBH', flags, m + 126, blen)
        else:
            header = struct.pack('!BBQ', flags, m + 127, blen)
        buf = header + mask + buf
        self.next_layer.write(buf)

    @override(Stream)
    def write_primitive(self, buf: bytes):
        self.write_frame(0x82, buf)

    @override(Stream)
    async def read_primitive(self) -> bytes:
        assert self.next_layer is not None
        buf = await self.next_layer.readexactly(2)
        flags, blen = struct.unpack('!BB', buf)
        m, blen = blen & 0x80, blen & 0x7f
        if blen == 126:
            buf = await self.next_layer.readexactly(2)
            blen, = struct.unpack('!H', buf)
        elif blen == 127:
            buf = await self.next_layer.readexactly(8)
            blen, = struct.unpack('!Q', buf)
        if m != 0:
            mask = await self.next_layer.readexactly(4)
            buf = await self.next_layer.readexactly(blen)
            buf = bytes(c ^ mask[i % 4] for i, c in enumerate(buf))
        else:
            buf = await self.next_layer.readexactly(blen)
        op = flags & 0xf
        if op == 8:  # close
            return b''
        if op in (1, 2):  # text/binary
            return buf
        if op == 9:  # ping
            self.write_frame(0x8a, buf)
            await self.drain()
        if op in (0, 9, 0xa):  # continue/ping/pong
            return await self.read()
        raise RuntimeError('invalid ws frame type')
