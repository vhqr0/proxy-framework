from abc import ABC, abstractmethod

from p3.stream.stream import Stream
from p3.utils.layerable import Layerable
from p3.utils.loggable import Loggable
from p3.utils.override import override


class Acceptor(Layerable['Acceptor'], Loggable, ABC):

    @abstractmethod
    async def accept(self) -> Stream:
        raise NotImplementedError


class WrappedAcceptor(Acceptor):
    stream: Stream

    def __init__(self, stream: Stream, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream

    @override(Acceptor)
    async def accept(self) -> Stream:
        return self.stream
