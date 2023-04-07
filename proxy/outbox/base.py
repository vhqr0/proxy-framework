import socket
import ssl
from timeit import timeit
from typing import Any, Optional

from ..common import Loggable, MappedSerializable, override
from ..defaults import (TLS_OUTBOX_CERT_FILE, TLS_OUTBOX_HOST,
                        WEIGHT_DECREASE_STEP, WEIGHT_INCREASE_STEP,
                        WEIGHT_INITIAL, WEIGHT_MAXIMAL, WEIGHT_MINIMAL)
from ..defaulturl import DefaultURL, OutboxDefaultURL
from ..inbox import Request
from ..stream import Stream


class Outbox(MappedSerializable['Outbox'], Loggable):
    url: DefaultURL
    name: str
    weight: float
    delay: float
    fetcher: str
    tcp_extra_kwargs: dict[str, Any]

    def __init__(self,
                 url: Optional[str] = None,
                 name: Optional[str] = None,
                 weight: float = WEIGHT_INITIAL,
                 delay: float = -1.0,
                 fetcher: str = '',
                 tcp_extra_kwargs: Optional[dict[str, Any]] = None,
                 **kwargs):
        super().__init__(**kwargs)
        if url is None:
            url = self.scheme + '://'
        self.url = OutboxDefaultURL(url)
        self.name = name if name is not None else self.__class__.__name__
        self.weight = weight
        self.delay = delay
        self.fetcher = fetcher
        self.tcp_extra_kwargs = tcp_extra_kwargs \
            if tcp_extra_kwargs is not None else dict()

    def __str__(self) -> str:
        return f'<{self.name} {self.weight}W>'

    def summary(self) -> str:
        return f'{self.fetcher}\t{self.scheme}://{self}\t{self.delay}'

    @override(MappedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = str(self.url)
        obj['name'] = self.name
        obj['weight'] = self.weight
        obj['delay'] = self.delay
        obj['fetcher'] = self.fetcher
        return obj

    @classmethod
    @override(MappedSerializable)
    def scheme_from_dict(cls, obj: dict[str, Any]) -> str:
        if 'scheme' in obj:
            return super().scheme_from_dict(obj)
        url = OutboxDefaultURL(obj.get('url') or '')
        return url.scheme

    @classmethod
    @override(MappedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj.get('url') or ''
        kwargs['name'] = obj.get('name') or cls.__name__
        kwargs['weight'] = obj.get('weight') or WEIGHT_INITIAL
        kwargs['delay'] = obj.get('delay') or -1.0
        kwargs['fetcher'] = obj.get('fetcher') or ''
        return kwargs

    def weight_increase(self):
        self.weight = min(self.weight + WEIGHT_INCREASE_STEP, WEIGHT_MAXIMAL)

    def weight_decrease(self):
        self.weight = max(self.weight - WEIGHT_DECREASE_STEP, WEIGHT_MINIMAL)

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

    async def connect(self, req: Request) -> Stream:
        raise NotImplementedError


class TLSCtxOutbox(Outbox):
    tls_cert_file: str
    tls_host: str
    tls_ctx: ssl.SSLContext

    def __init__(self,
                 tls_cert_file: str = TLS_OUTBOX_CERT_FILE,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.tls_cert_file = tls_cert_file
        self.tls_host = tls_host
        self.tls_ctx = ssl.create_default_context(
            cafile=self.tls_cert_file or None)
        self.tcp_extra_kwargs['ssl'] = self.tls_ctx
        self.tcp_extra_kwargs['server_hostname'] = self.tls_host

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['tls_cert_file'] = self.tls_cert_file
        obj['tls_host'] = self.tls_host
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['tls_cert_file'] = obj.get('tls_cert_file') or \
            TLS_OUTBOX_CERT_FILE
        kwargs['tls_host'] = obj.get('tls_host') or TLS_OUTBOX_HOST
        return kwargs
