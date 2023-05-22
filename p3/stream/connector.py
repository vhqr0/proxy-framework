from abc import ABC, abstractmethod

from p3.stream.stream import Stream
from p3.utils.layerable import Layerable
from p3.utils.loggable import Loggable


class Connector(Layerable['Connector'], Loggable, ABC):

    @abstractmethod
    async def connect(self, rest: bytes = b'') -> Stream:
        raise NotImplementedError
