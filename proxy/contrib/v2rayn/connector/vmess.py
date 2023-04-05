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
from proxy.stream import Stream

from ..stream import CounteredAESGCM, VmessStream


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
        assert len(rest) != 0

        key = random.randbytes(16)
        iv = random.randbytes(16)
        rv = random.getrandbits(8)
        rkey = md5(key).digest()
        riv = md5(iv).digest()
        write_encryptor = CounteredAESGCM(key, iv[2:12])
        read_decryptor = CounteredAESGCM(rkey, riv[2:12])
        ts = struct.pack('!Q', int(time.time()))
        addr, port = self.addr
        addr_bytes = addr.encode()
        alen = len(addr_bytes)
        plen = random.getrandbits(4)

        # ver(B)          : 1
        # iv(16s)         : iv
        # key(16s)        : key
        # rv(B)           : rv
        # opts(B)         : 1
        # plen|secmeth(B) : plen|3
        # res(B)          : 0
        # cmd(B)          : 1
        # port(H)         : port
        # atype(B)        : 2
        # alen(B)         : alen
        # addr({alen}s)   : addr
        # random({plen}s) : randbytes
        req = struct.pack(
            f'!B16s16sBBBBBHBB{alen}s{plen}s',
            1,
            iv,
            key,
            rv,
            1,
            (plen << 4) + 3,
            0,
            1,
            port,
            2,
            alen,
            addr_bytes,
            random.randbytes(plen),
        )
        req += self.fnv32a(req)
        cipher = Cipher(AES(self.reqkey), CFB(md5(4 * ts).digest()))
        encryptor = cipher.encryptor()
        req = encryptor.update(req) + encryptor.finalize()
        auth = HMAC(key=self.userid.bytes, msg=ts, digestmod='md5').digest()
        buf = write_encryptor.encrypt(rest)
        buf = struct.pack('!H', len(buf)) + buf
        req = auth + req + buf
        next_stream = await self.next_layer.connect(rest=req)

        try:
            buf = await next_stream.readexactly(4)
            cipher = Cipher(AES(rkey), CFB(riv))
            decryptor = cipher.decryptor()
            buf = decryptor.update(buf) + decryptor.finalize()
            if buf != struct.pack('!BBBB', rv, 0, 0, 0):
                raise RuntimeError('invalid vmess rv')
            return VmessStream(
                write_encryptor=write_encryptor,
                read_decryptor=read_decryptor,
                next_layer=next_stream,
            )
        except Exception as e:
            exc = e

        try:
            next_stream.close()
            await next_stream.wait_closed()
        except Exception:
            pass

        raise exc

    @staticmethod
    def fnv32a(buf: bytes) -> bytes:
        r, p, m = 0x811c9dc5, 0x01000193, 0xffffffff
        for c in buf:
            r = ((r ^ c) * p) & m
        return struct.pack('!I', r)
