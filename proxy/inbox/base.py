import dataclasses
import ssl
import asyncio

from typing import Any, Optional

from ..defaults import (
    INBOX_URL,
    TLS_INBOX_CERT_FILE,
    TLS_INBOX_KEY_FILE,
    TLS_INBOX_KEY_PWD,
)
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
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        self.url = InboxDefaultURL(url)
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

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


class TLSCtxInbox(Inbox):
    tls_cert_file: str
    tls_key_file: str
    tls_key_pwd: str
    tls_ctx: ssl.SSLContext

    def __init__(self,
                 tls_cert_file: str = TLS_INBOX_CERT_FILE,
                 tls_key_file: str = TLS_INBOX_KEY_FILE,
                 tls_key_pwd: str = TLS_INBOX_KEY_PWD,
                 **kwargs):
        super().__init__(**kwargs)
        self.tls_cert_file = tls_cert_file
        self.tls_key_file = tls_key_file
        self.tls_key_pwd = tls_key_pwd
        self.tls_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.tls_ctx.load_cert_chain(
            certfile=self.tls_cert_file,
            keyfile=self.tls_key_file,
            password=self.tls_key_pwd or None,
        )
        self.tcp_extra_kwargs['ssl'] = self.tls_ctx

    @override(Inbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['tls_cert_file'] = self.tls_cert_file
        obj['tls_key_file'] = self.tls_key_file
        obj['tls_key_pwd'] = self.tls_key_pwd
        return obj

    @classmethod
    @override(Inbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['tls_cert_file'] = obj.get('tls_cert_file') or \
            TLS_INBOX_CERT_FILE
        kwargs['tls_key_file'] = obj.get('tls_key_file') or TLS_INBOX_KEY_FILE
        kwargs['tls_key_pwd'] = obj.get('tls_key_pwd') or TLS_INBOX_KEY_PWD
        return kwargs
