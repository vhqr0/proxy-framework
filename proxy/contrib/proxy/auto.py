from proxy.common import override
from proxy.stream import ProxyAcceptor, Stream
from proxy.stream.errors import ProtocolError

from .http import HTTPAcceptor
from .socks5 import Socks5Acceptor


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
