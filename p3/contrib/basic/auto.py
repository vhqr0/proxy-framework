from p3.contrib.basic.http import HTTPAcceptor
from p3.contrib.basic.socks5 import Socks5Acceptor
from p3.iobox import Inbox, TLSCtxInbox
from p3.stream import Acceptor, ProxyAcceptor, ProxyRequest, Stream
from p3.stream.errors import ProtocolError
from p3.utils.override import override


class AutoAcceptor(HTTPAcceptor, Socks5Acceptor, ProxyAcceptor):

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            buf = await stream.peek()
            if len(buf) == 0:
                raise ProtocolError('auto', 'empty')
            if buf[0] == 5:
                await self.dispatch_socks5(stream)
            else:
                await self.dispatch_http(stream)
            return stream


class AutoInbox(Inbox):
    scheme = 'auto'

    @override(Inbox)
    async def accept_primitive(
        self,
        next_acceptor: Acceptor,
    ) -> tuple[Stream, ProxyRequest]:
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
