from ..common import override
from .base import Stream


class NULLStream(Stream):

    @override(Stream)
    def write_primitive(self, buf: bytes):
        pass

    @override(Stream)
    async def read_primitive(self) -> bytes:
        return b''
