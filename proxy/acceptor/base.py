from abc import ABC, abstractmethod

from ..common import Loggable, MultiLayer
from ..stream import Stream


class Acceptor(MultiLayer['Acceptor'], Loggable, ABC):

    @abstractmethod
    async def accept(self) -> Stream:
        raise NotImplementedError


class ProxyAcceptor(Acceptor):
    addr: tuple[str, int]
