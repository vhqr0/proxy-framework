import dataclasses
import asyncio

from typing import Any

from ..defaults import INBOX_URL
from ..common import override, Serializable, Loggable
from ..defaulturl import DefaultURL, InboxDefaultURL
from ..acceptor import Acceptor, TCPAcceptor
from ..stream import Stream


@dataclasses.dataclass
class Request:
    stream: Stream
    addr: tuple[str, int]
    rest: bytes

    def __str__(self):
        return f'<{self.addr[0]} {self.addr[1]} {len(self.rest)}B>'


class Inbox(Serializable, Loggable):
    scheme: str
    url: DefaultURL
    tcp_extra_kwargs: dict[str, Any]

    scheme_dict: dict[str, type['Inbox']] = dict()

    def __init__(self,
                 url: str = INBOX_URL,
                 tcp_extra_kwargs: dict[str, Any] = dict(),
                 **kwargs):
        super().__init__(**kwargs)
        self.url = InboxDefaultURL(url)
        self.tcp_extra_kwargs = tcp_extra_kwargs

    def __init_subclass__(cls, **kwargs):
        if hasattr(cls, 'scheme'):
            cls.scheme_dict[cls.scheme] = cls

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {'scheme': self.scheme, 'url': str(self.url)}

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'Inbox':
        if 'scheme' in obj:
            scheme = obj['scheme']
        else:
            url = InboxDefaultURL(obj.get('url') or '')
            scheme = url.scheme
        inbox_cls = cls.scheme_dict[scheme]
        kwargs = inbox_cls.kwargs_from_dict(obj)
        return inbox_cls(**kwargs)

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = {'url': obj.get('url') or INBOX_URL}
        return kwargs

    async def accept_from_tcp(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter) -> Request:
        next_acceptor = TCPAcceptor(reader=reader, writer=writer)
        return await self.accept(next_acceptor)

    async def accept(self, next_acceptor: Acceptor) -> Request:
        raise NotImplementedError
