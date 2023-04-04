import functools
from hashlib import sha224

from ..common import override
from ..acceptor import Acceptor, TrojanAcceptor
from .base import Request, TLSCtxInbox


class TrojanInbox(TLSCtxInbox):
    scheme = 'trojan'

    @functools.cached_property
    def auth(self) -> bytes:
        return sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxInbox)
    async def accept(self, next_acceptor: Acceptor) -> Request:
        acceptor = TrojanAcceptor(auth=self.auth, next_layer=next_acceptor)
        stream = await acceptor.accept()
        return Request(stream=stream, addr=acceptor.addr, rest=acceptor.rest)
