from functools import cached_property
from hashlib import sha224

from proxy.common import override
from proxy.server import Inbox, Outbox
from proxy.server.tlsctx import TLSCtxInbox, TLSCtxOutbox
from proxy.stream import Acceptor, ProxyRequest, Stream
from proxy.stream.common import TCPConnector

from .auto import AutoAcceptor
from .http import HTTPConnector
from .socks5 import Socks5Connector
from .trojan import TrojanAcceptor, TrojanConnector


class AutoInbox(Inbox):
    scheme = 'auto'

    @override(Inbox)
    async def accept_primitive(self, next_acceptor: Acceptor) -> ProxyRequest:
        acceptor = AutoAcceptor(next_layer=next_acceptor)
        return await ProxyRequest.from_acceptor(acceptor=acceptor)


class AutoSInbox(AutoInbox, TLSCtxInbox):
    scheme = 'autos'


class HTTPInbox(AutoInbox):
    scheme = 'http'


class Socks5Inbox(AutoInbox):
    scheme = 'socks5'


class Socks5hInbox(Socks5Inbox):
    scheme = 'socks5h'


class HTTPSInbox(AutoSInbox):
    scheme = 'https'


class Socks5SInbox(AutoSInbox):
    scheme = 'socks5s'


class Socks5hSInbox(AutoSInbox):
    scheme = 'socks5hs'


class HTTPOutbox(Outbox):
    scheme = 'http'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = HTTPConnector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)


class HTTPSOutbox(HTTPOutbox, TLSCtxOutbox):
    scheme = 'https'


class Socks5Outbox(Outbox):
    scheme = 'socks5'

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = Socks5Connector(addr=req.addr, next_layer=next_connector)
        return await connector.connect(rest=req.rest)


class Socks5hOutbox(Socks5Outbox):
    scheme = 'socks5h'


class Socks5SOutbox(Socks5Outbox, TLSCtxOutbox):
    scheme = 'socks5s'


class Socks5hSOutbox(Socks5SOutbox):
    scheme = 'socks5hs'


class TrojanInbox(TLSCtxInbox):
    scheme = 'trojan'

    @cached_property
    def auth(self) -> bytes:
        return sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxInbox)
    async def accept_primitive(self, next_acceptor: Acceptor) -> ProxyRequest:
        acceptor = TrojanAcceptor(auth=self.auth, next_layer=next_acceptor)
        return await ProxyRequest.from_acceptor(acceptor=acceptor)


class TrojanOutbox(TLSCtxOutbox):
    scheme = 'trojan'

    @cached_property
    def auth(self) -> bytes:
        return sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxOutbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = TCPConnector(
            tcp_extra_kwargs=self.tcp_extra_kwargs,
            addr=self.url.addr,
        )
        connector = TrojanConnector(
            auth=self.auth,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
