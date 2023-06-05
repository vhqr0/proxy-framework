from abc import ABC, abstractmethod
from random import randbytes
from typing import Optional

from p3.contrib.tls13.ciphers import (CipherSuite, CipherSuiteList,
                                      CompressionMethod, CompressionMethodList)
from p3.contrib.tls13.common import TLS13BEnum, Version
from p3.contrib.tls13.extension import ExtensionList
from p3.stream.buffer import Buffer
from p3.stream.structs import BStruct, IStruct
from p3.utils.override import override


class HandshakeType(TLS13BEnum):
    ClientHello = 1
    ServerHello = 2
    NewSessionTicket = 4
    EndOfEarlyData = 5
    EncryptedExtensions = 8
    Certificate = 11
    CertificateRequest = 13
    CertificateVerify = 15
    Finished = 20
    KeyUpdate = 24
    MessageHash = 254


class Handshake(ABC):
    msg_type: HandshakeType
    msg_dict: dict[int, type['Handshake']] = dict()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'msg_type'):
            cls.msg_dict[int(cls.msg_type)] = cls

    def __bytes__(self) -> bytes:
        buf = self.pack_handshake()
        return IStruct.pack((self.msg_type << 24) + len(buf)) + buf

    @abstractmethod
    def pack_handshake(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def pop_from_buffer(cls, buffer: Buffer) -> 'Handshake':
        msg_type = HandshakeType.pop_from_buffer(buffer)
        msg_cls = cls.msg_dict.get(int(msg_type))
        if msg_cls is None:
            msg_type.raise_protocol_error()
        assert msg_cls is not None
        return msg_cls.pop_msg_from_buffer(buffer)

    @classmethod
    @abstractmethod
    def pop_msg_from_buffer(cls, buffer: Buffer) -> 'Handshake':
        raise NotImplementedError


class ClientHello(Handshake):
    random: bytes  # 32s
    session_id: bytes  # 32s legacy
    cipher_suites: CipherSuiteList
    compression_methods: CompressionMethodList  # legacy
    extensions: ExtensionList

    msg_type = HandshakeType.ClientHello
    version = Version.TLS12  # legacy

    def __init__(
        self,
        extensions: ExtensionList,
        random: Optional[bytes] = None,
        session_id: Optional[bytes] = None,
        cipher_suites: Optional[CipherSuiteList] = None,
        compression_methods: Optional[CompressionMethodList] = None,
    ):
        if random is None:
            random = randbytes(32)
        if session_id is None:
            session_id = randbytes(32)
        if cipher_suites is None:
            cipher_suites = CipherSuiteList.defaults()
        if compression_methods is None:
            compression_methods = CompressionMethodList.defaults()
        self.random = random
        self.session_id = session_id
        self.cipher_suites = cipher_suites
        self.compression_methods = compression_methods
        self.extensions = extensions

    @override(Handshake)
    def pack_handshake(self) -> bytes:
        buf = bytes(self.version) + \
            self.random + \
            BStruct.pack_varlen(self.session_id)
        buf += bytes(self.cipher_suites)
        buf += bytes(self.compression_methods)
        buf += bytes(self.extensions)
        return buf

    @classmethod
    @abstractmethod
    def pop_msg_from_buffer(cls, buffer: Buffer) -> 'Handshake':
        version = Version.pop_from_buffer(buffer)
        cls.version.ensure(version)
        random = buffer.pop(32)
        session_id = BStruct.pop_varlen_from_buffer(buffer)
        cipher_suites = CipherSuiteList.pop_from_buffer(buffer)
        compression_methods = CompressionMethodList.pop_from_buffer(buffer)
        extensions = ExtensionList.pop_from_buffer(buffer)
        return cls(
            extensions=extensions,
            random=random,
            session_id=session_id,
            cipher_suites=cipher_suites,
            compression_methods=compression_methods,
        )


class ServerHello(Handshake):
    random: bytes
    session_id_echo: bytes  # 32 legacy
    cipher_suite: CipherSuite
    compression_method: CompressionMethod  # legacy
    extensions: ExtensionList

    HELLO_RETRY_MAGIC = bytes.fromhex(
        'CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C')

    msg_type = HandshakeType.ServerHello
    version = Version.TLS12

    def __init__(
        self,
        session_id_echo: bytes,
        extensions: ExtensionList,
        random: Optional[bytes] = None,
        cipher_suite: CipherSuite = CipherSuite.AES_128_GCM_SHA256,
        compression_method: CompressionMethod = CompressionMethod.
        NoCompression,
    ):
        if random is None:
            random = randbytes(32)
        self.random = random
        self.session_id_echo = session_id_echo
        self.cipher_suite = cipher_suite
        self.compression_method = compression_method
        self.extensions = extensions

    @override(Handshake)
    def pack_handshake(self) -> bytes:
        buf = bytes(self.version) + \
            self.random + \
            BStruct.pack_varlen(self.session_id_echo) + \
            bytes(self.cipher_suite) + \
            bytes(self.compression_method)
        buf += bytes(self.extensions)
        return buf

    def is_hello_retry(self) -> bool:
        return self.random == self.HELLO_RETRY_MAGIC


class EndOfEarlyData(Handshake):
    msg_type = HandshakeType.EndOfEarlyData


class EncryptedExtensions(Handshake):
    msg_type = HandshakeType.EncryptedExtensions


class CertificateRequest(Handshake):
    msg_type = HandshakeType.CertificateRequest


class Certificate(Handshake):
    msg_type = HandshakeType.Certificate


class CertificateVerify(Handshake):
    msg_type = HandshakeType.CertificateVerify


class Finished(Handshake):
    msg_type = HandshakeType.Finished


class NewSessionTicket(Handshake):
    msg_type = HandshakeType.NewSessionTicket


class KeyUpdate(Handshake):
    msg_type = HandshakeType.NewSessionTicket
