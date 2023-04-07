import ssl
from typing import Any

from proxy.common import override
from proxy.connector import Connector, TCPConnector, WSConnector
from proxy.defaults import TLS_OUTBOX_HOST, WS_OUTBOX_HOST, WS_OUTBOX_PATH
from proxy.stream import Stream


class V2rayNNetConnector(Connector):
    addr: tuple[str, int]
    net: str
    ws_path: str
    ws_host: str
    tls_host: str

    def __init__(self,
                 addr: tuple[str, int],
                 net: str = 'tcp',
                 ws_path: str = WS_OUTBOX_PATH,
                 ws_host: str = WS_OUTBOX_HOST,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.addr = addr
        self.net = net
        self.ws_path = ws_path
        self.ws_host = ws_host
        self.tls_host = tls_host

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        tcp_extra_kwargs: dict[str, Any] = dict()
        if self.net in ('tls', 'wss'):
            tcp_extra_kwargs['ssl'] = ssl.create_default_context()
            tcp_extra_kwargs['server_hostname'] = self.tls_host
        connector: Connector
        connector = TCPConnector(
            tcp_extra_kwargs=tcp_extra_kwargs,
            addr=self.addr,
        )
        if self.net in ('ws', 'wss'):
            connector = WSConnector(
                path=self.ws_path,
                host=self.ws_host,
                next_layer=connector,
            )
        return await connector.connect(rest=rest)
