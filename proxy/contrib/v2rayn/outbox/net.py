from abc import ABC
from typing import Any

from proxy.common import override
from proxy.defaults import TLS_OUTBOX_HOST, WS_OUTBOX_HOST, WS_OUTBOX_PATH
from proxy.outbox import Outbox


class V2rayNNetCtxOutbox(Outbox, ABC):
    net: str
    ws_path: str
    ws_host: str
    tls_host: str

    def __init__(self,
                 net: str = 'tcp',
                 ws_path: str = WS_OUTBOX_PATH,
                 ws_host: str = WS_OUTBOX_HOST,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.net = net
        self.ws_path = ws_path
        self.ws_host = ws_host
        self.tls_host = tls_host

    def __str__(self) -> str:
        return f'<{self.net} {self.name} {self.weight}W>'

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['net'] = self.net
        obj['ws_path'] = self.ws_path
        obj['ws_host'] = self.ws_host
        obj['tls_host'] = self.tls_host
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['net'] = obj.get('net') or 'tcp'
        kwargs['ws_path'] = obj.get('ws_path') or WS_OUTBOX_PATH
        kwargs['ws_host'] = obj.get('ws_host') or WS_OUTBOX_HOST
        kwargs['tls_host'] = obj.get('tls_host') or TLS_OUTBOX_HOST
        return kwargs
