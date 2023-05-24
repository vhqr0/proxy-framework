from abc import ABC, abstractmethod
from typing import Any, Optional

from p3.defaults import INBOX_URL
from p3.stream import Acceptor, ProxyRequest
from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import DispatchedSerializable
from p3.utils.url import URL


class Inbox(DispatchedSerializable['Inbox'], Loggable, ABC):
    url: URL
    tcp_extra_kwargs: dict[str, Any]

    ensure_rest: bool = True
    fallback_url = URL.from_str(INBOX_URL)

    def __init__(
        self,
        url: Optional[str] = None,
        tcp_extra_kwargs: Optional[dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        if tcp_extra_kwargs is None:
            tcp_extra_kwargs = dict()
        self.url = URL.from_str(url, fallback=self.fallback_url)
        self.tcp_extra_kwargs = tcp_extra_kwargs

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
        url = URL.from_str(obj.get('url') or '', fallback=cls.fallback_url)
        return url.scheme

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or ''
        return kwargs

    async def accept(self, next_acceptor: Acceptor) -> ProxyRequest:
        req = await self.accept_primitive(next_acceptor=next_acceptor)
        if self.ensure_rest:
            await req.ensure_rest()
        return req

    @abstractmethod
    async def accept_primitive(self, next_acceptor: Acceptor) -> ProxyRequest:
        raise NotImplementedError
