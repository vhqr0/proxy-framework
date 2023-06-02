"""Trojan protocol implementation.

Links:
  https://trojan-gfw.github.io/trojan/protocol
"""
from dataclasses import dataclass
from functools import cached_property
from hashlib import sha224

from typing_extensions import Self

from p3.common.tcp import TCPConnector
from p3.contrib.basic.socks5 import Socks5Addr, Socks5Atyp, Socks5Cmd
from p3.iobox import TLSCtxInbox, TLSCtxOutbox
from p3.stream import (Acceptor, ProxyAcceptor, ProxyConnector, ProxyRequest,
                       Stream)
from p3.stream.errors import ProtocolError
from p3.stream.structs import BStruct
from p3.utils.override import override


@dataclass
class TrojanRequest:
    """
    +-----+------+----------+----------+
    | CMD | ATYP | DST.ADDR | DST.PORT |
    +-----+------+----------+----------+
    |  1  |  1   | Variable |    2     |
    +-----+------+----------+----------+
    """
    cmd: Socks5Cmd
    dst: Socks5Addr

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        _cmd = await stream.readB()
        cmd = Socks5Cmd(_cmd)
        dst = await Socks5Addr.read_from_stream(stream)
        return cls(cmd, dst)

    def pack(self) -> bytes:
        return BStruct.pack(self.cmd) + self.dst.pack()


@dataclass
class TrojanHeader:
    """
    +-----------------------+---------+----------------+---------+----------+
    | hex(SHA224(password)) |  CRLF   | Trojan Request |  CRLF   | Payload  |
    +-----------------------+---------+----------------+---------+----------+
    |          56           | X'0D0A' |    Variable    | X'0D0A' | Variable |
    +-----------------------+---------+----------------+---------+----------+
    """
    auth: bytes
    req: TrojanRequest

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        auth = await stream.readuntil(b'\r\n', strip=True)
        if len(auth) != 56:
            raise ProtocolError('trojan', 'crlf')
        req = await TrojanRequest.read_from_stream(stream)
        empty = await stream.readuntil(b'\r\n', strip=True)
        if len(empty) != 0:
            raise ProtocolError('trojan', 'crlf')
        return cls(auth, req)

    def pack(self) -> bytes:
        return self.auth + b'\r\n' + self.req.pack() + b'\r\n'


class TrojanConnector(ProxyConnector):
    auth: bytes

    ensure_next_layer = True

    def __init__(self, auth: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(auth) == 56
        self.auth = auth

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        dst = Socks5Addr(Socks5Atyp.DOMAINNAME, self.addr)
        treq = TrojanRequest(Socks5Cmd.Connect, dst)
        req = TrojanHeader(self.auth, treq).pack()
        if len(rest) != 0:
            req += rest
        return await self.next_layer.connect(rest=req)


class TrojanAcceptor(ProxyAcceptor):
    auth: bytes

    ensure_next_layer = True

    def __init__(self, auth: bytes, **kwargs):
        super().__init__(**kwargs)
        assert len(auth) == 56
        self.auth = auth

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            header = await TrojanHeader.read_from_stream(stream)
            auth, req = header.auth, header.req
            if auth != self.auth:
                raise ProtocolError('trojan', 'auth')
            if req.cmd != Socks5Cmd.Connect:
                raise ProtocolError('trojan', 'cmd', req.cmd.name)
            return stream


class TrojanInbox(TLSCtxInbox):
    scheme = 'trojan'

    @cached_property
    def auth(self) -> bytes:
        return sha224(self.url.pwd.encode()).hexdigest().encode()

    @override(TLSCtxInbox)
    async def accept_primitive(
        self,
        next_acceptor: Acceptor,
    ) -> tuple[Stream, ProxyRequest]:
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
