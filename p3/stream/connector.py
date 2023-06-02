from abc import ABC, abstractmethod

from p3.stream.stream import Stream
from p3.utils.layerable import Layerable
from p3.utils.loggable import Loggable
from p3.utils.override import override


class Connector(Layerable['Connector'], Loggable, ABC):

    @abstractmethod
    async def connect(self, rest: bytes = b'') -> Stream:
        raise NotImplementedError


class StreamWrappedConnector(Connector):
    stream: Stream

    def __init__(self, stream: Stream, **kwargs):
        super().__init__(**kwargs)
        self.stream = stream

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        if len(rest) != 0:
            await self.stream.writedrain(rest)
        return self.stream
