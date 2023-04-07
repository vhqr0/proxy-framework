"""Vmess client side protocol implementation.

Links:
  https://www.v2fly.org/developer/protocols/vmess.html
"""
from functools import cached_property
from hashlib import md5
from typing import Any
from uuid import UUID

from proxy.common import override
from proxy.connector import Connector, TCPConnector, WSConnector
from proxy.inbox import Request
from proxy.outbox import Outbox
from proxy.stream import Stream

from ..connector import VmessConnector


class VmessOutbox(Outbox):
    userid: UUID
    net: str
    ws_path: str
    ws_host: str

    scheme = 'vmess'

    VMESS_MAGIC = b'c48619fe-8f02-49e0-b9e9-edf763e17e21'

    def __init__(self,
                 userid: str,
                 net: str = 'tcp',
                 ws_path: str = '/',
                 ws_host: str = 'localhost',
                 **kwargs):
        super().__init__(**kwargs)
        self.userid = UUID(userid)
        self.net = net
        self.ws_path = ws_path
        self.ws_host = ws_host

    def __str__(self) -> str:
        return f'<{self.net} {self.name} {self.weight}W>'

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['userid'] = str(self.userid)
        obj['net'] = self.net
        obj['ws_path'] = self.ws_path
        obj['ws_host'] = self.ws_host
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['userid'] = obj['userid']
        kwargs['net'] = obj.get('net') or 'tcp'
        kwargs['ws_path'] = obj.get('ws_path') or '/'
        kwargs['ws_host'] = obj.get('ws_host') or 'localhost'
        return kwargs

    @cached_property
    def reqkey(self) -> bytes:
        return md5(self.userid.bytes + self.VMESS_MAGIC).digest()

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        next_connector: Connector
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        if self.net in ('ws', 'wss'):
            next_connector = WSConnector(
                next_layer=next_connector,
                path=self.ws_path,
                host=self.ws_host,
            )
        connector = VmessConnector(
            userid=self.userid,
            reqkey=self.reqkey,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
