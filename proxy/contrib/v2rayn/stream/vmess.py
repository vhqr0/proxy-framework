import struct
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from proxy.common import override
from proxy.stream import Stream


class CounteredAESGCM:
    aesgcm: AESGCM
    iv: bytes
    count: int

    def __init__(self, key: bytes, iv: bytes, count: int = 0):
        self.aesgcm = AESGCM(key)
        self.iv = iv
        self.count = count

    def encrypt(self, buf: bytes) -> bytes:
        iv = struct.pack('!H', self.count) + self.iv
        buf = self.aesgcm.encrypt(iv, buf, b'')
        self.count += 1
        return buf

    def decrypt(self, buf: bytes) -> bytes:
        iv = struct.pack('!H', self.count) + self.iv
        buf = self.aesgcm.decrypt(iv, buf, b'')
        self.count += 1
        return buf


class VmessStream(Stream):
    write_encryptor: CounteredAESGCM
    read_decryptor: CounteredAESGCM

    def __init__(self, write_encryptor: CounteredAESGCM,
                 read_decryptor: CounteredAESGCM, **kwargs):
        super().__init__(**kwargs)
        self.write_encryptor = write_encryptor
        self.read_decryptor = read_decryptor

    @override(Stream)
    def close(self):
        exc: Optional[Exception] = None
        try:
            self.write(b'')
        except Exception as e:
            exc = e
        try:
            super().close()
        except Exception as e:
            if exc is None:
                exc = e
        if exc is not None:
            raise exc

    @override(Stream)
    def write(self, buf: bytes):
        assert self.next_layer is not None
        buf = self.write_encryptor.encrypt(buf)
        buf = struct.pack('!H', len(buf)) + buf
        self.next_layer.write(buf)

    @override(Stream)
    async def read(self) -> bytes:
        assert self.next_layer is not None
        buf = self.pop()
        if len(buf) != 0:
            return buf
        buf = await self.next_layer.readexactly(2)
        blen, = struct.unpack('!H', buf)
        buf = await self.next_layer.readexactly(blen)
        buf = self.read_decryptor.decrypt(buf)
        return buf
