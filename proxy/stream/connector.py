from abc import ABC, abstractmethod

from proxy.stream.stream import Stream
from proxy.utils.layerable import Layerable
from proxy.utils.loggable import Loggable


class Connector(Layerable['Connector'], Loggable, ABC):

    @abstractmethod
    async def connect(self, rest: bytes = b'') -> Stream:
        raise NotImplementedError
