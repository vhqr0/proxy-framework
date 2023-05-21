from abc import ABC, abstractmethod

from proxy.stream.stream import Stream
from proxy.utils.layerable import Layerable
from proxy.utils.loggable import Loggable
from proxy.utils.override import override


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
