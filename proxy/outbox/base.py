import timeit
import socket
import ssl

from typing import Any, Optional

from ..defaults import (
    TLS_OUTBOX_CERT_FILE,
    TLS_OUTBOX_HOST,
    WEIGHT_INITIAL,
    WEIGHT_MINIMAL,
    WEIGHT_MAXIMAL,
    WEIGHT_INCREASE_STEP,
    WEIGHT_DECREASE_STEP,
)
from ..common import override, Serializable, Loggable
from ..defaulturl import DefaultURL, OutboxDefaultURL
from ..stream import Stream
from ..inbox import Request


class Outbox(Serializable, Loggable):
    scheme: str
    url: DefaultURL
    name: str
    weight: float
    delay: float
    fetcher: str
    tcp_extra_kwargs: dict[str, Any]

    scheme_dict: dict[str, type['Outbox']] = dict()

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

    def __init_subclass__(cls, **kwargs):
        if hasattr(cls, 'scheme'):
            cls.scheme_dict[cls.scheme] = cls

    def __str__(self) -> str:
        return f'<{self.name} {self.weight}W>'

    def summary(self) -> str:
        return f'{self.name}\t{self.weight}W\t{self.delay}D'

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'scheme': self.scheme,
            'url': str(self.url),
            'name': self.name,
            'weight': self.weight,
            'delay': self.delay,
            'fetcher': self.fetcher,
        }

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'Outbox':
        if 'scheme' in obj:
            scheme = obj['scheme']
        else:
            url = OutboxDefaultURL(obj.get('url') or '')
            scheme = url.scheme
        outbox_cls = cls.scheme_dict[scheme]
        kwargs = outbox_cls.kwargs_from_dict(obj)
        return outbox_cls(**kwargs)

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = {
            'url': obj.get('url') or '',
            'name': obj.get('name') or cls.__name__,
            'weight': obj.get('weight') or WEIGHT_INITIAL,
            'delay': obj.get('delay') or -1.0,
            'fetcher': obj.get('fetcher') or '',
        }
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
            self.delay = timeit.timeit(connect, number=1)
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
