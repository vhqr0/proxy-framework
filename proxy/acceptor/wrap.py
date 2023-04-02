from ..common import override
from ..stream import Stream
from .base import Acceptor


class WrapAcceptor(Acceptor):
    stream: Stream

    def __init__(self, stream: Stream, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream

    @override(Acceptor)
    async def accept(self) -> Stream:
        return self.stream
