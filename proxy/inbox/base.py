import dataclasses
import functools
import asyncio

from yarl import URL

from typing import Any

from ..defaults import INBOX_URL
from ..common import override, Serializable, Loggable
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
    addr: tuple[str, int]
    tcp_extra_kwargs: dict[str, Any]

    scheme_dict: dict[str, type['Inbox']] = dict()

    def __init__(self,
                 addr: tuple[str, int],
                 tcp_extra_kwargs: dict[str, Any] = dict(),
                 **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.tcp_extra_kwargs = tcp_extra_kwargs

    def __init_subclass__(cls, **kwargs):
        if hasattr(cls, 'scheme'):
            cls.scheme_dict[cls.scheme] = cls

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {'scheme': self.scheme, 'url': self.url}

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'Inbox':
        if 'scheme' in obj:
            scheme = obj['scheme']
        elif 'url' in obj:
            scheme = cls.parseurl(obj['url']).scheme
        else:
            scheme = INBOX_URL.scheme
        inbox_cls = cls.scheme_dict[scheme]
        kwargs = inbox_cls.kwargs_from_dict(obj)
        return inbox_cls(**kwargs)

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        url = cls.parseurl(obj.get('url') or str(INBOX_URL))
        kwargs = {'addr': (url.host, url.port)}
        return kwargs

    @functools.cached_property
    def url(self) -> str:
        url = URL.build(
            scheme=self.scheme,
            host=self.addr[0],
            port=self.addr[1],
        )
        return str(url)

    @classmethod
    def parseurl(cls, url: str) -> URL:
        assert INBOX_URL.host is not None and \
            INBOX_URL.port is not None
        u = URL(url)
        if len(u.scheme) == 0:
            if hasattr(cls, 'scheme'):
                scheme = cls.scheme
            else:
                scheme = INBOX_URL.scheme
            u = u.with_scheme(scheme)
        if u.host is None:
            u = u.with_host(INBOX_URL.host)
        if u.port is None:
            u = u.with_port(INBOX_URL.port)
        return u

    async def accept_from_tcp(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter) -> Request:
        next_acceptor = TCPAcceptor(reader=reader, writer=writer)
        return await self.accept(next_acceptor)

    async def accept(self, next_acceptor: Acceptor) -> Request:
        raise NotImplementedError
