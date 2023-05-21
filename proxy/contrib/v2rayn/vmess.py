"""Vmess client side protocol implementation.

Links:
  https://www.v2fly.org/developer/protocols/vmess.html
"""
import random
import time
from functools import cached_property
from hashlib import md5
from hmac import HMAC
from struct import Struct
from typing import Any
from uuid import UUID

from Crypto.Hash.SHAKE128 import SHAKE128_XOF
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CFB

from proxy.contrib.v2rayn.defaults import STREAM_VMESS_BUFSIZE
from proxy.contrib.v2rayn.net import V2rayNNetConnector, V2rayNNetCtxOutbox
from proxy.iobox import Outbox
from proxy.stream import ProxyConnector, ProxyRequest, Stream
from proxy.stream.errors import BufferOverflowError, ProtocolError
from proxy.stream.structs import HStruct, IStruct, QStruct
from proxy.utils.override import override

BBBBStruct = Struct('!BBBB')

# ver(B)          : 1
# iv(16s)         : iv
# key(16s)        : key
# rv(B)           : rv
# opts(B)         : 5 (standard, mask)
# plen|secmeth(B) : plen|3 (aes-128-gcm)
# res(B)          : 0
# cmd(B)          : 1 (tcp connect)
# port(H)         : port
# atype(B)        : 2 (domain)
# alen(B)         : alen
# addr({alen}s)   : addr
# random({plen}s) : randbytes
ReqStruct = Struct('!B16s16sBBBBBHBB')


def fnv32a(buf: bytes) -> bytes:
    r, p, m = 0x811c9dc5, 0x01000193, 0xffffffff
    for c in buf:
        r = ((r ^ c) * p) & m
    return IStruct.pack(r)


class VmessCryptor:
    shake: SHAKE128_XOF
    aead: AESGCM
    iv: bytes
    count: int

    def __init__(self, key: bytes, iv: bytes, count: int = 0):
        self.shake = SHAKE128_XOF(iv)
        self.aead = AESGCM(key)
        self.iv = iv[2:12]
        self.count = count

    def encrypt(self, buf: bytes) -> bytes:
        mask, = HStruct.unpack(self.shake.read(2))
        iv = HStruct.pack(self.count) + self.iv
        self.count = (self.count + 1) & 0xffff

        buf = self.aead.encrypt(iv, buf, b'')
        buf = HStruct.pack(len(buf) ^ mask) + buf

        return buf

    async def read_decrypt_from_stream(self, stream: Stream) -> bytes:
        mask, = HStruct.unpack(self.shake.read(2))
        iv = HStruct.pack(self.count) + self.iv
        self.count = (self.count + 1) & 0xffff

        blen = await stream.readH()
        blen = blen ^ mask
        if blen > STREAM_VMESS_BUFSIZE:
            raise BufferOverflowError(blen)
        buf = await stream.readexactly(blen)
        buf = self.aead.decrypt(iv, buf, b'')

        return buf


class VmessStream(Stream):
    write_encryptor: VmessCryptor
    read_decryptor: VmessCryptor

    def __init__(self, write_encryptor: VmessCryptor,
                 read_decryptor: VmessCryptor, **kwargs):
        super().__init__(**kwargs)
        self.write_encryptor = write_encryptor
        self.read_decryptor = read_decryptor

    @override(Stream)
    def write_primitive(self, buf: bytes):
        assert self.next_layer is not None
        buf = self.write_encryptor.encrypt(buf)
        self.next_layer.write(buf)

    @override(Stream)
    async def read_primitive(self) -> bytes:
        assert self.next_layer is not None
        buf = await self.next_layer.peek()
        if len(buf) == 0:
            return b''
        return await self.read_decryptor.read_decrypt_from_stream(
            self.next_layer)


class VmessConnector(ProxyConnector):
    userid: UUID
    reqkey: bytes

    ensure_next_layer = True

    def __init__(self, userid: UUID, reqkey: bytes, **kwargs):
        super().__init__(**kwargs)
        self.userid = userid
        self.reqkey = reqkey

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None

        if len(rest) == 0:
            raise ValueError('rest cannot be empty')

        key = random.randbytes(16)
        iv = random.randbytes(16)
        rv = random.getrandbits(8)
        rkey = md5(key).digest()
        riv = md5(iv).digest()
        write_encryptor = VmessCryptor(key, iv)
        read_decryptor = VmessCryptor(rkey, riv)
        ts = QStruct.pack(int(time.time()))
        addr, port = self.addr
        addr_bytes = addr.encode()
        alen = len(addr_bytes)
        plen = random.getrandbits(4)

        req = ReqStruct.pack(1, iv, key, rv, 5, (plen << 4) + 3, 0, 1, port, 2,
                             alen)
        req = req + addr_bytes + random.randbytes(plen)
        req += fnv32a(req)
        cipher = Cipher(AES(self.reqkey), CFB(md5(4 * ts).digest()))
        encryptor = cipher.encryptor()
        req = encryptor.update(req) + encryptor.finalize()
        auth = HMAC(key=self.userid.bytes, msg=ts, digestmod='md5').digest()
        buf = write_encryptor.encrypt(rest)
        req = auth + req + buf

        next_stream = await self.next_layer.connect(rest=req)
        async with next_stream.cm(exc_only=True):
            buf = await next_stream.peek()
            if len(buf) == 0:
                raise ProtocolError('vmess', 'header', 'emptycheck')
            buf = await next_stream.readexactly(4)
            cipher = Cipher(AES(rkey), CFB(riv))
            decryptor = cipher.decryptor()
            buf = decryptor.update(buf) + decryptor.finalize()
            rrv, opt, cmd, clen = BBBBStruct.unpack(buf)
            if rrv != rv:
                raise ProtocolError('vmess', 'header', 'auth')
            if opt != 0:
                raise ProtocolError('vmess', 'header', 'opt')
            if cmd != 0 or clen != 0:
                raise ProtocolError('vmess', 'header', 'cmd')
            return VmessStream(
                write_encryptor=write_encryptor,
                read_decryptor=read_decryptor,
                next_layer=next_stream,
            )


class VmessOutbox(V2rayNNetCtxOutbox):
    userid: UUID

    scheme = 'vmess'

    VMESS_MAGIC = b'c48619fe-8f02-49e0-b9e9-edf763e17e21'

    def __init__(self, userid: str, **kwargs):
        super().__init__(**kwargs)
        self.userid = UUID(userid)

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['userid'] = str(self.userid)
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['userid'] = obj['userid']
        return kwargs

    @cached_property
    def reqkey(self) -> bytes:
        return md5(self.userid.bytes + self.VMESS_MAGIC).digest()

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = V2rayNNetConnector(
            addr=self.url.addr,
            net=self.net,
            ws_path=self.ws_path,
            ws_host=self.ws_host,
            tls_host=self.tls_host,
        )
        connector = VmessConnector(
            userid=self.userid,
            reqkey=self.reqkey,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
