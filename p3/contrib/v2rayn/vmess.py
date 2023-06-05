"""Vmess client side protocol implementation.

Links:
  https://www.v2fly.org/en_US/developer/protocols/vmess.html
  https://github.com/v2fly/v2fly-github-io/blob/master/docs/en_US/developer/protocols/vmess.md
"""
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import auto
from functools import cached_property
from hashlib import md5
from hmac import HMAC
from random import getrandbits, randbytes
from typing import Any, Optional
from uuid import UUID

from Crypto.Hash.SHAKE128 import SHAKE128_XOF
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CFB
from typing_extensions import Self

from p3.contrib.v2rayn.net import V2rayNNetCtxOutbox
from p3.iobox import Outbox
from p3.stream import ProxyConnector, ProxyRequest, Stream
from p3.stream.enums import BaseEnumMixin, BEnum, BFlag
from p3.stream.errors import BufferOverflowError, ProtocolError
from p3.stream.structs import BaseStruct, BStruct, HStruct, QStruct
from p3.utils.fnv import fnv32a
from p3.utils.override import override


class VmessEnumMixin(BaseEnumMixin):
    scheme = 'vmess'


class VmessBEnum(VmessEnumMixin, BEnum):
    pass


class VmessBFlag(VmessEnumMixin, BFlag):  # type: ignore
    pass


class VmessUserID(UUID):
    VMESS_MAGIC = b'c48619fe-8f02-49e0-b9e9-edf763e17e21'

    def certification(self, ts: bytes) -> bytes:
        return HMAC(key=self.bytes, msg=ts, digestmod=md5).digest()

    @cached_property
    def instruction_key(self) -> bytes:
        return md5(self.bytes + self.VMESS_MAGIC).digest()

    @staticmethod
    def instruction_iv(ts: bytes) -> bytes:
        return md5(4 * ts).digest()


class VmessVer(VmessBEnum):
    V1 = 1


class VmessOption(VmessBFlag):
    """
    | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
    |:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
    | X | X | X | A | P | M | R | S |

    * S (0x01): standard format data stream (recommended to open);
    * R (0x02): The client expects to reuse TCP connections
                (V2Ray 2.23+ deprecated);
      * This item is valid only when S is turned on;
    * M (0x04): Turn on metadata obfuscation (recommended);
      * This item is valid only when S is turned on;
      * When the item is turned on, the client and the server need to
        construct two Shake instances respectively, namely
        RequestMask = Shake (request data IV) and
        ResponseMask = Shake (response data IV).
    * X: reserved

    2023-05-23: The English doc is outdated, I add this:

    * P (0x08): Turn on global padding;
      * This item is valid only when M is turned on;
      * Sec can only be AES-128-GCM or ChaCha20-Poly1305;
      * When the item is turned on, the client and the server generate
        random length padding bytes based on the Shake instance and
        attach them to the cipher text.
    * A (0x10): Turned on experimental cipher text length authentication;
    """
    S, R, M, P, A = auto(), auto(), auto(), auto(), auto()


class VmessServerOption(VmessBFlag):
    """
    * 0x01: The server is ready to reuse TCP connection
            (V2Ray 2.23+ is deprecated);
    """
    R = auto()


class VmessEncryptionMethod(VmessBEnum):
    """
    * 0x00: AES-128-CFB;
    * 0x01: No encryption;
    * 0x02: AES-128-GCM;
    * 0x03: ChaCha20-Poly1305;

    2023-05-24: The English doc is outdated, the specific is:

    * 0x01：Legacy (AES-128-CFB)；
    * 0x03：AES-128-GCM；
    * 0x04：ChaCha20-Poly1305；
    * 0x05：None；

    I have been debugging for this for so long. :-)
    """
    AES128CFB = 1
    AES128GCM = 3
    ChaCha20Poly1305 = 4
    NoEncryption = 5


class VmessCommand(VmessBEnum):
    """
    * 0x01: TCP data;
    * 0x02: UDP data;
    """
    TCP = 1
    UDP = 2


class VmessServerCommand(VmessBEnum):
    """
    * 0x01: dynamic port instruction
    """
    NoCommand = 0
    DynamicPort = 1


class VmessAddressType(VmessBEnum):
    """
    * 0x01: IPv4
    * 0x02: domain name
    * 0x03: IPv6
    """
    IPv4 = 1
    IPv6 = 3
    DomainName = 2


@dataclass
class VmessAddress:
    t: VmessAddressType
    addr: tuple[str, int]

    HBStruct = BaseStruct('!HB')
    IPv4Struct = BaseStruct('!HB4s')
    IPv6Struct = BaseStruct('!HB16s')

    def __bytes__(self) -> bytes:
        addr, port = self.addr
        if self.t is VmessAddressType.DomainName:
            addr_bytes = addr.encode()
            return self.HBStruct.pack(port, self.t) + \
                BStruct.pack_varlen(addr_bytes)
        elif self.t is VmessAddressType.IPv4:
            addr_bytes = socket.inet_pton(socket.AF_INET, addr)
            return self.IPv4Struct.pack(port, self.t, addr_bytes)
        elif self.t is VmessAddressType.IPv6:
            addr_bytes = socket.inet_pton(socket.AF_INET6, addr)
            return self.IPv6Struct.pack(port, self.t, addr_bytes)
        else:
            self.t.raise_protocol_error()


class VmessInstruction:
    """
    | 1 byte             | 16 bytes           | 16 bytes            |
    |:------------------:|:------------------:|:-------------------:|
    | Version number Ver | Data encryption IV | Data encryption Key |

    | 1 byte                    | 1 byte     | 4 bit    |
    |:-------------------------:|:----------:|:--------:|
    | Response authentication V | Option Opt | Margin P |

    | 4 bit                 | 1 byte | 1 byte      | 2 bytes   |
    |:---------------------:|:------:|:-----------:|:---------:|
    | Encryption method Sec | Keep   | Command Cmd | Port Port |

    | 1 byte         | N bytes   | P byte       | 4 bytes |
    |:--------------:|:---------:|:------------:|:-------:|
    | Address type T | Address A | Random value | Check F |
    """
    iv: bytes
    key: bytes
    v: int
    opt: VmessOption
    p: int
    sec: VmessEncryptionMethod
    cmd: VmessCommand
    a: VmessAddress

    BBBBBStruct = BaseStruct('!BBBBB')

    def __init__(
        self,
        a: VmessAddress,
        iv: Optional[bytes] = None,
        key: Optional[bytes] = None,
        v: Optional[int] = None,
        opt: VmessOption = VmessOption.S | VmessOption.M,
        p: Optional[int] = None,
        sec: VmessEncryptionMethod = VmessEncryptionMethod.AES128GCM,
        cmd: VmessCommand = VmessCommand.TCP,
    ):
        if iv is None:
            iv = randbytes(16)
        if key is None:
            key = randbytes(16)
        if v is None:
            v = getrandbits(8)
        if p is None:
            p = getrandbits(4)
        self.iv = iv
        self.key = key
        self.v = v
        self.opt = opt
        self.p = p
        self.sec = sec
        self.cmd = cmd
        self.a = a

    @cached_property
    def riv(self) -> bytes:
        return md5(self.iv).digest()

    @cached_property
    def rkey(self) -> bytes:
        return md5(self.key).digest()

    def __bytes__(self) -> bytes:
        buf = bytes(VmessVer.V1) + \
            self.iv + \
            self.key
        buf += self.BBBBBStruct.pack(
            self.v,
            self.opt.value,
            (self.p << 4) + self.sec,
            0,
            self.cmd,
        )
        buf += bytes(self.a) + randbytes(self.p)
        buf += fnv32a(buf)
        return buf


@dataclass
class VmessRequest:
    """
    | 16 bytes                  | X bytes          | The rest  |
    |---------------------------|------------------|-----------|
    | Certification Information | Instruction part | Data part |
    """
    userid: VmessUserID
    instruction: VmessInstruction

    def __bytes__(self) -> bytes:
        ts = QStruct.pack(int(time.time()))
        certification = self.userid.certification(ts)
        key = self.userid.instruction_key
        iv = VmessUserID.instruction_iv(ts)
        cipher = Cipher(AES(key), CFB(iv))
        encryptor = cipher.encryptor()
        instruction = bytes(self.instruction)
        instruction = encryptor.update(instruction)
        return certification + instruction


@dataclass
class VmessResponse:
    """
    | 1 byte                    | 1 byte     | 1 byte      |
    |---------------------------|------------|-------------|
    | Response authentication V | Option Opt | Command Cmd |

    | 1 byte           | M bytes             | The rest             |
    |------------------|---------------------|----------------------|
    | Command length M | Instruction content | Actual response data |
    """
    v: int
    opt: VmessServerOption
    cmd: VmessServerCommand
    content: Optional[bytes]

    BBBBStruct = BaseStruct('!BBBB')

    @classmethod
    async def read_from_stream(
        cls,
        stream: Stream,
        instruction: VmessInstruction,
    ) -> Self:
        cipher = Cipher(AES(instruction.rkey), CFB(instruction.riv))
        decryptor = cipher.decryptor()
        buf = await stream.readexactly(cls.BBBBStruct.size)
        buf = decryptor.update(buf)
        v, opt, cmd, m = cls.BBBBStruct.unpack_with_types(
            buf, int, VmessServerOption, VmessServerCommand, int)
        if v != instruction.v:
            raise ProtocolError('vmess', 'auth')
        content: Optional[bytes] = None
        if m != 0:
            content = await stream.readexactly(m)
            content = decryptor.update(content)
        return cls(v, opt, cmd, content)


class VmessCryptor(ABC):
    VMESS_BUFSIZE = 2**14  # 16KB
    VMESS_PACK_BUFSIZE = 2**13  # 8KB

    def encrypt(self, buf: bytes) -> bytes:
        assert len(buf) != 0
        ebuf = b''
        while len(buf) > self.VMESS_PACK_BUFSIZE:
            ebuf += self.pack_encrypt(buf[:self.VMESS_PACK_BUFSIZE])
            buf = buf[self.VMESS_PACK_BUFSIZE:]
        if len(buf) != 0:
            ebuf += self.pack_encrypt(buf)
        return ebuf

    @abstractmethod
    def pack_encrypt(self, buf: bytes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    async def read_decrypt_from_stream(self, stream: Stream) -> bytes:
        raise NotImplementedError


class _VmessMaskedGCMCryptor(VmessCryptor):
    """
    Vmess cryptor with opt(M|S) and sec(AES128GCM).
    """
    shake: SHAKE128_XOF
    aead: AESGCM
    iv: bytes
    count: int

    def __init__(self, key: bytes, iv: bytes, count: int = 0):
        self.shake = SHAKE128_XOF(iv)
        self.aead = AESGCM(key)
        self.iv = iv[2:12]
        self.count = count

    @override(VmessCryptor)
    def pack_encrypt(self, buf: bytes) -> bytes:
        assert len(buf) <= self.VMESS_PACK_BUFSIZE
        mask, = HStruct.unpack(self.shake.read(2))
        iv = HStruct.pack(self.count) + self.iv
        self.count = (self.count + 1) & 0xffff
        buf = self.aead.encrypt(iv, buf, b'')
        buf = HStruct.pack(len(buf) ^ mask) + buf
        return buf

    @override(VmessCryptor)
    async def read_decrypt_from_stream(self, stream: Stream) -> bytes:
        mask, = HStruct.unpack(self.shake.read(2))
        iv = HStruct.pack(self.count) + self.iv
        self.count = (self.count + 1) & 0xffff
        blen, = await HStruct.read_from_stream(stream)
        blen = blen ^ mask
        if blen > self.VMESS_BUFSIZE:
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
    userid: VmessUserID

    ensure_next_layer = True

    def __init__(self, userid: VmessUserID, **kwargs):
        super().__init__(**kwargs)
        self.userid = userid

    @override(ProxyConnector)
    async def connect(self, rest: bytes = b'') -> Stream:
        assert self.next_layer is not None
        if len(rest) == 0:
            raise ProtocolError('vmess', 'rest')

        addr = VmessAddress(VmessAddressType.DomainName, self.addr)
        instruction = VmessInstruction(addr)
        req = bytes(VmessRequest(self.userid, instruction))

        write_encryptor = _VmessMaskedGCMCryptor(
            instruction.key,
            instruction.iv,
        )
        read_decryptor = _VmessMaskedGCMCryptor(
            instruction.rkey,
            instruction.riv,
        )
        req += write_encryptor.encrypt(rest)

        next_stream = await self.next_layer.connect(rest=req)
        async with next_stream.cm(exc_only=True):
            buf = await next_stream.peek()
            if len(buf) == 0:
                raise ProtocolError('vmess', 'empty')
            resp = await VmessResponse.read_from_stream(
                next_stream, instruction)
            VmessServerOption(0).ensure(resp.opt)
            VmessServerCommand.NoCommand.ensure(resp.cmd)
            if resp.content is not None:
                raise ProtocolError('vmess', 'content')
            return VmessStream(
                write_encryptor=write_encryptor,
                read_decryptor=read_decryptor,
                next_layer=next_stream,
            )


class VmessOutbox(V2rayNNetCtxOutbox):
    userid: VmessUserID

    scheme = 'vmess'

    def __init__(self, userid: str, **kwargs):
        super().__init__(**kwargs)
        self.userid = VmessUserID(userid)

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

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        next_connector = self.v2rayn_net_connector()
        connector = VmessConnector(
            userid=self.userid,
            addr=req.addr,
            next_layer=next_connector,
        )
        return await connector.connect(rest=req.rest)
