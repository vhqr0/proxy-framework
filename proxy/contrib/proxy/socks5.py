import socket
from enum import IntEnum, unique
from struct import Struct

from proxy.common import override
from proxy.stream import ProxyAcceptor, ProxyConnector, Stream
from proxy.stream.errors import ProtocolError
from proxy.stream.structs import BStruct, HStruct

BBStruct = Struct('!BB')
BBBStruct = Struct('!BBB')
BBBBStruct = Struct('!BBBB')
BBBBBStruct = Struct('!BBBBB')
IPv4Struct = Struct('!4sH')
IPv6Struct = Struct('!16sH')


@unique
class Ver(IntEnum):
    V5 = 5


@unique
class Rsv(IntEnum):
    Empty = 0


@unique
class Auth(IntEnum):
    NoAuth = 0
    GSSAPI = 1
    Pwd = 2
    NoMeth = 0xff


@unique
class Rep(IntEnum):
    Succeeded = 0
    Failure = 1
    Rules = 2
    NetUnreach = 3
    HostUnreach = 4
    ConnRefused = 5
    TTLExpired = 6
    CmdSupport = 7
    AtypeSupport = 8


@unique
class Cmd(IntEnum):
    Connect = 1
    Bind = 2
    UdpAssoc = 3


@unique
class Atype(IntEnum):
    Domain = 3
    IPv4 = 1
    IPv6 = 4

    async def read_addr_from_stream(self, stream: Stream) -> tuple[str, int]:
        if self is self.Domain:
            alen = await stream.readB()
            addr_bytes = await stream.readexactly(alen)
            port = await stream.readH()
            addr = addr_bytes.decode()
        elif self is self.IPv4:
            addr_bytes, port = await stream.read_struct(IPv4Struct)
            addr = socket.inet_ntop(socket.AF_INET, addr_bytes)
        elif self is self.IPv6:
            addr_bytes, port = await stream.read_struct(IPv6Struct)
            addr = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            raise ProtocolError('socks5', 'atype', self.name)
        return addr, port

    def pack_addr(self, addr: tuple[str, int]) -> bytes:
        if self is self.Domain:
            addr_bytes = addr[0].encode()
            alen = len(addr_bytes)
            addr_bytes = BStruct.pack(alen) + addr_bytes
        elif self is self.IPv4:
            addr_bytes = socket.inet_pton(socket.AF_INET, addr[0])
        elif self is self.IPv6:
            addr_bytes = socket.inet_pton(socket.AF_INET6, addr[0])
        else:
            raise ProtocolError('socks5', 'atype', self.name)
        port = addr[1]
        return BStruct.pack(self) + addr_bytes + HStruct.pack(port)


class Socks5Connector(ProxyConnector):
    SOCKS5_AUTH_REQ = BBBStruct.pack(Ver.V5, 1, Auth.NoAuth)
    SOCKS5_AUTH_RES = BBStruct.pack(Ver.V5, Auth.NoAuth)

    ensure_next_layer = True

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.connect(self.SOCKS5_AUTH_REQ)
        async with stream.cm(exc_only=True):
            buf = await stream.readexactly(2)
            if buf != self.SOCKS5_AUTH_RES:
                raise ProtocolError('socks5', 'auth', 'header')
            addr, port = self.addr
            addr_bytes = addr.encode()
            req = BBBBBStruct.pack(
                Ver.V5,
                Cmd.Connect,
                Rsv.Empty,
                Atype.Domain,
                len(addr_bytes),
            ) + addr_bytes + HStruct.pack(port)
            await stream.writedrain(req)
            _ver, _rep, _rsv, _atype = await stream.read_struct(BBBBStruct)
            _, rep, _, atype = Ver(_ver), Rep(_rep), Rsv(_rsv), Atype(_atype)
            if rep != Rep.Succeeded:
                raise ProtocolError('socks5', 'header', 'rep', rep.name)
            await atype.read_addr_from_stream(stream)
            if len(rest) != 0:
                await stream.writedrain(rest)
            return stream


class Socks5Acceptor(ProxyAcceptor):
    SOCKS5_AUTH_RES = BBStruct.pack(Ver.V5, Auth.NoAuth)
    SOCKS5_RES = BBBStruct.pack(Ver.V5, Rep.Succeeded, Rsv.Empty) + \
        Atype.IPv4.pack_addr(('0.0.0.0', 0))

    ensure_next_layer = True

    @override(ProxyAcceptor)
    async def accept(self) -> Stream:
        assert self.next_layer is not None
        stream = await self.next_layer.accept()
        async with stream.cm(exc_only=True):
            await self.dispatch_socks5(stream)
            return stream

    async def dispatch_socks5(self, stream: Stream):
        _ver, nmeths = await stream.read_struct(BBStruct)
        ver = Ver(_ver)
        if ver != Ver.V5 or nmeths == 0:
            raise ProtocolError('socks5', 'auth', 'header')
        meths = await stream.readexactly(nmeths)
        if Auth.NoAuth not in meths:
            raise ProtocolError('socks5', 'auth', 'meth')
        await stream.writedrain(self.SOCKS5_AUTH_RES)
        _ver, _cmd, _rsv, _atype = await stream.read_struct(BBBBStruct)
        _, cmd, _, atype = Ver(_ver), Cmd(_cmd), Rsv(_rsv), Atype(_atype)
        if cmd != Cmd.Connect:
            raise ProtocolError('socks5', 'header', 'cmd', cmd.name)
        self.addr = await atype.read_addr_from_stream(stream)
        await stream.writedrain(self.SOCKS5_RES)
