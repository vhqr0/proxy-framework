from typing_extensions import Self
from typing import Optional

from ..common import Loggable, MultiLayer
from ..stream import Stream


class Acceptor(MultiLayer['Acceptor'], Loggable):
    next_layer: Optional[Self]

    async def accept(self) -> Stream:
        raise NotImplementedError


class ProxyAcceptor(Acceptor):
    addr: tuple[str, int]
    rest: bytes
