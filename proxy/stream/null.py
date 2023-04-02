from ..common import override
from .base import Stream


class NULLStream(Stream):

    @override(Stream)
    def write(self, buf: bytes):
        pass

    @override(Stream)
    async def read(self) -> bytes:
        buf = self.pop()
        if len(buf) != 0:
            return buf
        return b''
