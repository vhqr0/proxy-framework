from typing_extensions import Self

from p3.contrib.tls13.common import TLS13BEnum, TLS13HEnum, TLS13IntEnumList
from p3.stream.structs import BStruct, HStruct
from p3.utils.override import override


class CompressionMethod(TLS13BEnum):
    NoCompression = 0


class CompressionMethodList(TLS13IntEnumList):
    struct = BStruct
    enum_type = CompressionMethod

    @classmethod
    @override(TLS13IntEnumList)
    def defaults(cls) -> Self:
        return cls([])


class CipherSuite(TLS13HEnum):

    AES_128_GCM_SHA256 = 0x1301
    AES_256_GCM_SHA384 = 0x1302
    CHACHA20_POLY1305_SHA256 = 0x1303
    AES_128_CCM_SHA256 = 0x1304
    AES_128_CCM_8_SHA256 = 0x1305


class CipherSuiteList(TLS13IntEnumList):
    struct = HStruct
    enum_type = CipherSuite

    @classmethod
    @override(TLS13IntEnumList)
    def defaults(cls) -> Self:
        return cls([
            CipherSuite.AES_128_GCM_SHA256,
            CipherSuite.AES_256_GCM_SHA384,
            CipherSuite.CHACHA20_POLY1305_SHA256,
        ])


class SignatureScheme(TLS13HEnum):

    RSA_PKCS1_SHA256 = 0x0401
    RSA_PKCS1_SHA384 = 0x0501
    RSA_PKCS1_SHA512 = 0x0601

    ECDSA_SECP256R1_SHA256 = 0x0403
    ECDSA_SECP256R1_SHA384 = 0x0503
    ECDSA_SECP256R1_SHA512 = 0x0603

    RSA_PSS_RSAE_SHA256 = 0x0804
    RSA_PSS_RSAE_SHA384 = 0x0805
    RSA_PSS_RSAE_SHA512 = 0x0806

    ED25519 = 0x0807
    ED448 = 0x0808

    RSA_PKCS1_SHA1 = 0x0201
    ECDSA_SHA1 = 0x0203


class SignatureSchemeList(TLS13IntEnumList):
    struct = HStruct
    enum_type = SignatureScheme


class NamedGroup(TLS13HEnum):
    SECP256R1 = 0x0017
    SECP384R1 = 0x0018
    SECP521R1 = 0x0019
    X25519 = 0x001d
    X448 = 0x001e
    FFDHE2048 = 0x0100
    FFDHE3072 = 0x0101
    FFDHE4096 = 0x0102
    FFDHE6144 = 0x0103
    FFDHE8192 = 0x0104


class NamedGroupList(TLS13IntEnumList):
    struct = HStruct
    enum_type = NamedGroup

    @classmethod
    @override(TLS13IntEnumList)
    def defaults(cls) -> Self:
        return cls([NamedGroup.X25519])
