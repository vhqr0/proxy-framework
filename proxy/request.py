from dataclasses import dataclass

from typing_extensions import Self

from .acceptor import ProxyAcceptor
from .stream import Stream


@dataclass
class Request:
    stream: Stream
    addr: tuple[str, int]
    rest: bytes

    def __str__(self):
        return f'<{self.addr[0]} {self.addr[1]} {len(self.rest)}B>'

    @classmethod
    async def from_acceptor(cls, acceptor: ProxyAcceptor) -> Self:
        stream = await acceptor.accept()
        addr = acceptor.addr
        rest = stream.pop()
        return cls(stream=stream, addr=addr, rest=rest)

    async def ensure_rest(self):
        if len(self.rest) == 0:
            self.rest = await self.stream.readatleast(1)
