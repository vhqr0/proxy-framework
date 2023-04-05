"""Vmess client side protocol implementation.

Links:
  https://www.v2fly.org/developer/protocols/vmess.html
"""
from functools import cached_property
from hashlib import md5
from typing import Any
from uuid import UUID

from proxy.common import override
from proxy.connector import TCPConnector
from proxy.inbox import Request
from proxy.outbox import Outbox
from proxy.stream import Stream

from ..connector import VmessConnector


class VmessOutbox(Outbox):
    userid: UUID

    scheme = 'vmess'

    VMESS_MAGIC = b'c48619fe-8f02-49e0-b9e9-edf763e17e21'

    def __init__(self, userid: str, **kwargs):
        super().__init__(**kwargs)
        self.userid = UUID(userid)

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['userid'] = str(self.userid)
        return obj

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['userid'] = obj['userid']
        return kwargs

    @cached_property
    def reqkey(self) -> bytes:
        return md5(self.userid.bytes + self.VMESS_MAGIC).digest()

    @override(Outbox)
    async def connect(self, req: Request) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = VmessConnector(
            userid=self.userid,
            reqkey=self.reqkey,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
