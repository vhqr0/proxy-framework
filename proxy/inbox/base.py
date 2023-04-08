import asyncio
import ssl
from typing import Any, Optional

from ..acceptor import Acceptor, TCPAcceptor
from ..common import DispatchedSerializable, Loggable, override
from ..defaults import (INBOX_URL, TLS_INBOX_CERT_FILE, TLS_INBOX_KEY_FILE,
                        TLS_INBOX_KEY_PWD)
from ..defaulturl import DefaultURL, InboxDefaultURL
from ..request import Request


class Inbox(DispatchedSerializable['Inbox'], Loggable):
    url: DefaultURL
    tcp_extra_kwargs: dict[str, Any]

    ensure_rest: bool = True

    def __init__(self,
                 url: Optional[str] = None,
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        self.url = InboxDefaultURL(url)
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
        url = InboxDefaultURL(obj.get('url') or '')
        return url.scheme

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or INBOX_URL
        return kwargs

    async def accept_from_tcp(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter) -> Request:
        next_acceptor = TCPAcceptor(reader=reader, writer=writer)
        return await self.accept(next_acceptor=next_acceptor)

    async def accept(self, next_acceptor: Acceptor) -> Request:
        req = await self.accept_primitive(next_acceptor=next_acceptor)
        if self.ensure_rest:
            await req.ensure_rest()
        return req

    async def accept_primitive(self, next_acceptor: Acceptor) -> Request:
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
