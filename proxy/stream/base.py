from typing_extensions import Self
from typing import Optional

from ..common import Loggable, MultiLayer


class Stream(MultiLayer['Stream'], Loggable):
    next_layer: Optional[Self]
    to_read: bytes

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.to_read = b''

    def push(self, buf: bytes):
        self.to_read = buf + self.to_read

    def pop(self) -> bytes:
        buf, self.to_read = self.to_read, b''
        return buf

    def close(self):
        if self.next_layer is not None:
            self.next_layer.close()

    async def wait_closed(self):
        if self.next_layer is not None:
            await self.next_layer.wait_closed()

    def write_eof(self):
        if self.next_layer is not None:
            self.next_layer.write_eof()

    def write(self, buf: bytes):
        raise NotImplementedError

    async def drain(self):
        if self.next_layer is not None:
            await self.next_layer.drain()

    async def read(self) -> bytes:
        buf = self.pop()
        if len(buf) != 0:
            return buf
        raise NotImplementedError

    async def peek(self) -> bytes:
        if len(self.to_read) == 0:
            self.to_read = await self.read()
        return self.to_read
