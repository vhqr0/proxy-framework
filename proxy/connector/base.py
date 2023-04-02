from typing_extensions import Self
from typing import Optional

from ..common import Loggable, MultiLayer
from ..stream import Stream


class Connector(MultiLayer['Connector'], Loggable):
    next_layer: Optional[Self]

    async def connect(self, rest: bytes = b'') -> Stream:
        raise NotImplementedError
