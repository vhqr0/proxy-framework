import asyncio
import socket
from abc import ABC, abstractmethod
from timeit import timeit
from typing import Any, Optional

from ..common import DispatchedSerializable, Loggable, override
from ..defaults import WEIGHT_INITIAL
from ..stream import Acceptor, ProxyRequest, Stream
from ..stream.common import TCPAcceptor
from .weightable import Weightable
from .fallbackurl import FallbackURL, InboxFallbackURL, OutboxFallbackURL


class Inbox(DispatchedSerializable['Inbox'], Loggable, ABC):
    url: FallbackURL
    tcp_extra_kwargs: dict[str, Any]

    ensure_rest: bool = True

    def __init__(self,
                 url: Optional[str] = None,
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        self.url = InboxFallbackURL(url)
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = str(self.url)
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def scheme_from_dict(cls, obj: dict[str, Any]) -> str:
        if 'scheme' in obj:
            return super().scheme_from_dict(obj)
        url = InboxFallbackURL(obj.get('url') or '')
        return url.scheme

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or ''
        return kwargs

    async def accept_from_tcp(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter) -> ProxyRequest:
        next_acceptor = TCPAcceptor(reader=reader, writer=writer)
        return await self.accept(next_acceptor=next_acceptor)

    async def accept(self, next_acceptor: Acceptor) -> ProxyRequest:
        req = await self.accept_primitive(next_acceptor=next_acceptor)
        if self.ensure_rest:
            await req.ensure_rest()
        return req

    @abstractmethod
    async def accept_primitive(self, next_acceptor: Acceptor) -> ProxyRequest:
        raise NotImplementedError


class Outbox(DispatchedSerializable['Outbox'], Weightable, Loggable, ABC):
    url: FallbackURL
    name: str
    delay: float
    fetcher: str
    tcp_extra_kwargs: dict[str, Any]

    def __init__(self,
                 url: Optional[str] = None,
                 name: Optional[str] = None,
                 delay: float = -1.0,
                 fetcher: str = '',
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        self.url = OutboxFallbackURL(url)
        self.name = name if name is not None else self.__class__.__name__
        self.delay = delay
        self.fetcher = fetcher
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    def __str__(self) -> str:
        return f'<{self.name} {self.weight}W>'

    def summary(self) -> str:
        return f'{self.fetcher}\t{self.scheme}://{self}\t{self.delay}'

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = str(self.url)
        obj['name'] = self.name
        obj['weight'] = self.weight
        obj['delay'] = self.delay
        obj['fetcher'] = self.fetcher
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def scheme_from_dict(cls, obj: dict[str, Any]) -> str:
        if 'scheme' in obj:
            return super().scheme_from_dict(obj)
        url = OutboxFallbackURL(obj.get('url') or '')
        return url.scheme

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or ''
        kwargs['name'] = obj.get('name') or cls.__name__
        kwargs['weight'] = obj.get('weight') or WEIGHT_INITIAL
        kwargs['delay'] = obj.get('delay') or -1.0
        kwargs['fetcher'] = obj.get('fetcher') or ''
        return kwargs

    def ping(self):

        def connect():
            sock = socket.create_connection(self.url.addr, 2)
            sock.close()

        self.delay, self.weight = -1.0, -1.0
        try:
            self.delay = timeit(connect, number=1)
            self.weight = WEIGHT_INITIAL
        except Exception:
            pass

    @abstractmethod
    async def connect(self, req: ProxyRequest) -> Stream:
        raise NotImplementedError


class Fetcher(DispatchedSerializable['Fetcher'], Loggable, ABC):
    url: str
    name: str

    def __init__(self, url: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.name = name

    def __str__(self) -> str:
        return f'<{self.scheme}://{self.name}>'

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = self.url
        obj['name'] = self.name
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj['url']
        kwargs['name'] = obj['name']
        return kwargs

    @abstractmethod
    def fetch(self) -> list[Outbox]:
        raise NotImplementedError
