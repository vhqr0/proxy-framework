import random
import struct

from typing import Optional

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
    def close(self):
        exc: Optional[Exception] = None
        try:
            self.write_frame(0x88, b'')
        except Exception as e:
            exc = e
        try:
            super().close()
        except Exception as e:
            if exc is None:
                exc = e
        if exc is not None:
            raise exc

    @override(Stream)
    async def wait_closed(self):
        exc: Optional[Exception] = None
        try:
            await self.drain()
        except Exception as e:
            exc = e
        try:
            super().wait_closed()
        except Exception as e:
            if exc is None:
                exc = e
        if exc is not None:
            raise exc

    @override(Stream)
    def write(self, buf: bytes):
        self.write_frame(0x82, buf)

    @override(Stream)
    async def read(self) -> bytes:
        assert self.next_layer is not None
        buf = self.pop()
        if len(buf) != 0:
            return buf
        buf = await self.next_layer.read()
        if len(buf) < 2:
            buf + await self.next_layer.read()
        flags, blen = struct.unpack_from('!BB', buffer=buf, offset=0)
        buf = buf[2:]
        m, blen = blen & 0x80, blen & 0x7f
        if blen == 126:
            blen = struct.unpack_from('!H', buffer=buf, offset=0)
            buf = buf[2:]
        elif blen == 127:
            blen = struct.unpack_from('!Q', buffer=buf, offset=0)
            buf = buf[8:]
        if m != 0:
            mask, buf = buf[:4], buf[4:]
        while len(buf) < blen:
            next_buf = await self.next_layer.read()
            if len(next_buf) == 0:
                raise RuntimeError('invalid ws frame length')
            buf += next_buf
        if len(buf) > blen:
            self.next_layer.push(buf[blen:])
            buf = buf[:blen]
        if m != 0:
            buf = bytes(c ^ mask[i % 4] for i, c in enumerate(buf))
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
