from proxy.contrib.basic.http import HTTPAcceptor
from proxy.contrib.basic.socks5 import Socks5Acceptor
from proxy.iobox import Inbox, TLSCtxInbox
from proxy.stream import Acceptor, ProxyAcceptor, ProxyRequest, Stream
from proxy.stream.errors import ProtocolError
from proxy.utils.override import override


class AutoAcceptor(HTTPAcceptor, Socks5Acceptor, ProxyAcceptor):

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            buf = await stream.peek()
            if len(buf) == 0:
                raise ProtocolError('auto', 'emptycheck')
            if buf[0] == 5:
                await self.dispatch_socks5(stream)
            else:
                await self.dispatch_http(stream)
            return stream


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


class HTTPSInbox(AutoSInbox):
    scheme = 'https'


class Socks5Inbox(AutoInbox):
    scheme = 'socks5'


class Socks5SInbox(AutoSInbox):
    scheme = 'socks5s'
