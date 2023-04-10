from Crypto.Hash.SHAKE128 import SHAKE128_XOF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from proxy.common import override
from proxy.stream import Stream
from proxy.stream.errors import BufferOverflowError
from proxy.stream.structs import HStruct

from ..defaults import STREAM_VMESS_BUFSIZE


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

    async def read_decrypt(self, stream: Stream) -> bytes:
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
        return await self.read_decryptor.read_decrypt(self.next_layer)
