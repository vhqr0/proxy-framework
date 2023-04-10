import random
import struct
import time
from hashlib import md5
from hmac import HMAC
from uuid import UUID

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CFB

from proxy.common import override
from proxy.connector import ProxyConnector
from proxy.stream import ProtocolError, Stream

from ..stream import VmessCryptor, VmessStream


def fnv32a(buf: bytes) -> bytes:
    r, p, m = 0x811c9dc5, 0x01000193, 0xffffffff
    for c in buf:
        r = ((r ^ c) * p) & m
    return struct.pack('!I', r)


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
        ts = struct.pack('!Q', int(time.time()))
        addr, port = self.addr
        addr_bytes = addr.encode()
        alen = len(addr_bytes)
        plen = random.getrandbits(4)

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
        req = struct.pack(
            f'!B16s16sBBBBBHBB{alen}s{plen}s',
            1,
            iv,
            key,
            rv,
            5,
            (plen << 4) + 3,
            0,
            1,
            port,
            2,
            alen,
            addr_bytes,
            random.randbytes(plen),
        )
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
            rrv, opt, cmd, clen = struct.unpack('!BBBB', buf)
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
