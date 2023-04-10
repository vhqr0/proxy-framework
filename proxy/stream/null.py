from ..common import override
from .base import Stream


class NULLStream(Stream):

    def __init__(self, buf: bytes = b'', **kwargs):
        super().__init__(**kwargs)
        self.to_read = buf

    @override(Stream)
    def write_primitive(self, buf: bytes):
        pass

    @override(Stream)
    async def read_primitive(self) -> bytes:
        return b''
