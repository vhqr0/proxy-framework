import functools
import timeit
import socket

from yarl import URL

from typing import Any, Optional

from ..defaults import (
    OUTBOX_URL,
    WEIGHT_INITIAL,
    WEIGHT_MINIMAL,
    WEIGHT_MAXIMAL,
    WEIGHT_INCREASE_STEP,
    WEIGHT_DECREASE_STEP,
)
from ..common import override, Serializable, Loggable
from ..stream import Stream
from ..inbox import Request


class Outbox(Serializable, Loggable):
    scheme: str
    name: str
    weight: float
    delay: float

    scheme_dict: dict[str, type['Outbox']] = dict()

    def __init__(self,
                 name: Optional[str] = None,
                 weight: float = WEIGHT_INITIAL,
                 delay: float = -1.0,
                 **kwargs):
        super().__init__(**kwargs)
        self.name = name if name is not None else self.__class__.__name__
        self.weight = weight
        self.delay = delay

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
            'url': self.url,
            'name': self.name,
            'weight': self.weight,
            'delay': self.delay,
        }

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'Outbox':
        if 'scheme' in obj:
            scheme = obj['scheme']
        elif 'url' in obj:
            scheme = cls.parseurl(obj['url']).scheme
        else:
            scheme = OUTBOX_URL.scheme
        outbox_cls = cls.scheme_dict[scheme]
        kwargs = outbox_cls.kwargs_from_dict(obj)
        return outbox_cls(**kwargs)

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = {
            'name': obj.get('name') or cls.__name__,
            'weight': obj.get('weight') or WEIGHT_INITIAL,
            'delay': obj.get('delay') or -1.0,
        }
        return kwargs

    @functools.cached_property
    def url(self) -> str:
        url = URL.build(scheme=self.scheme)
        return str(url)

    @classmethod
    def parseurl(cls, url: str) -> URL:
        assert OUTBOX_URL.host is not None and \
            OUTBOX_URL.port is not None
        u = URL(url)
        if len(u.scheme) == 0:
            if hasattr(cls, 'scheme'):
                scheme = cls.scheme
            else:
                scheme = OUTBOX_URL.scheme
            u = u.with_scheme(scheme)
        if u.host is None:
            u = u.with_host(OUTBOX_URL.host)
        if u.port is None:
            u = u.with_port(OUTBOX_URL.port)
        return u

    def weight_increase(self):
        self.weight = min(self.weight + WEIGHT_INCREASE_STEP, WEIGHT_MAXIMAL)

    def weight_decrease(self):
        self.weight = max(self.weight - WEIGHT_DECREASE_STEP, WEIGHT_MINIMAL)

    def ping(self):
        self.delay = 0.0
        self.weight = WEIGHT_INITIAL

    async def connect(self, req: Request) -> Stream:
        raise NotImplementedError


class PeerOutbox(Outbox):
    addr: tuple[str, int]

    def __init__(self, addr: tuple[str, int], **kwargs):
        super().__init__(**kwargs)
        self.addr = addr

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        url = cls.parseurl(obj.get('url') or str(OUTBOX_URL))
        kwargs['addr'] = url.host, url.port
        return kwargs

    @functools.cached_property
    @override(Outbox)
    def url(self) -> str:
        url = URL.build(
            scheme=self.scheme,
            host=self.addr[0],
            port=self.addr[1],
        )
        return str(url)

    def ping_connect(self):
        sock = socket.create_connection(self.addr, 2)
        sock.close()

    @override(Outbox)
    def ping(self):
        self.delay = -1.0
        self.weight = -1.0
        try:
            self.delay = timeit.timeit(self.ping_connect, number=1)
            self.weight = WEIGHT_INITIAL
        except Exception:
            pass
