from typing_extensions import Self
from typing import Optional

from ..common import Loggable, MultiLayer
from ..stream import Stream


class Connector(MultiLayer['Connector'], Loggable):
    next_layer: Optional[Self]

    async def connect(self, rest: bytes = b'') -> Stream:
        raise NotImplementedError


class ProxyConnector(Connector):
    addr: tuple[str, int]

    def __init__(self, addr: tuple[str, int], **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
