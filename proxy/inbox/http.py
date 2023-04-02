from ..common import override
from ..acceptor import Acceptor, HTTPAcceptor
from .base import Request, Inbox


class HTTPInbox(Inbox):
    scheme = 'http'

    @override(Inbox)
    async def accept(self, next_acceptor: Acceptor) -> Request:
        acceptor = HTTPAcceptor(next_layer=next_acceptor)
        stream = await acceptor.accept()
        return Request(stream=stream, addr=acceptor.addr, rest=acceptor.rest)
