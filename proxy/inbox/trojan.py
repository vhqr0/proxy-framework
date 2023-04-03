import functools
import hashlib

from ..common import override
from ..acceptor import Acceptor, TrojanAcceptor
from .base import Request, Inbox


class TrojanInbox(Inbox):
    scheme = 'trojan'

    @functools.cached_property
    def pwd_hash(self) -> bytes:
        return hashlib.sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(Inbox)
    async def accept(self, next_acceptor: Acceptor) -> Request:
        acceptor = TrojanAcceptor(pwd=self.pwd_hash, next_layer=next_acceptor)
        stream = await acceptor.accept()
        return Request(stream=stream, addr=acceptor.addr, rest=acceptor.rest)
