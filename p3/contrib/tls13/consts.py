from enum import IntEnum, unique


@unique
class ContentType(IntEnum):
    Invalid = 0
    ChangeCipherSpec = 20
    Alert = 21
    Handshake = 22
    ApplicationData = 23
    Heartbeat = 24


@unique
class Version(IntEnum):
    SSL30 = 0x0300
    TLS10 = 0x0301
    TLS11 = 0x0302
    TLS12 = 0x0303
    TLS13 = 0x0304


@unique
class HandshakeType(IntEnum):
    HelloRequest = 0
    ClientHello = 1
    ServerHello = 2
    HelloVerifyRequest = 3
    NewSessionTicket = 4
    EndOfEarlyData = 5
    EncryptedExtensions = 8
    Certificate = 11
    ServerKeyExchange = 12
    CertificateRequest = 13
    ServerHelloDone = 14
    CertificateVerify = 15
    ClientKeyExchange = 16
    Finished = 20
    CertificateURL = 21
    CertificateStatus = 22
    SupplementalData = 23
    KeyUpdate = 24
    MessageHash = 254


@unique
class ExtensionType(IntEnum):
    ServerName = 0
    MaxFragmentLength = 1
    ClientCertificateURL = 2
    TrustedCAKeys = 3
    TruncatedHMAC = 4
    StatusRequest = 5
    UserMapping = 6
    ClientAuthz = 7
    ServerAuthz = 8
    CertType = 9
    SupportedGroups = 0xa
    ECPointFormats = 0xb
    SecureRemotePasswprd = 0xc
    SignatureAlgorithms = 0xd
    UseSRTP = 0xc
    Heartbeat = 0xf
    ApplicationLayerProtocolNegotiation = 0x10
    StatusRequestV2 = 0x11
    SignedCertificateTimestamp = 0x12
    ClientCertificateType = 0x13
    ServerCertificateType = 0x14
    Padding = 0x15
    EncryptThenMAC = 0x16
    ExtendedMasterSecret = 0x17
    TokenBinding = 0x18
    CachedInfo = 0x19
    TLSLTS = 0x1a
    CompressCertificate = 0x1b
    RecordSizeLimit = 0x1c
    PasswordProtect = 0x1d
    PasswordClear = 0x1e
    PasswordSalt = 0x1f
    SessionTicket = 0x23
    PreSharedKey = 0x29
    EarlyDataIndication = 0x2a
    SupportedVersion = 0x2b
    Cookie = 0x2c
    PSKKeyExchangeModes = 0x2d
    TicketEarlyDataInfo = 0x2e
    CertificateAuthorities = 0x2f
    OIDFilters = 0x30
    PostHandshakeAuth = 0x31
    SignatureAlgorithmsCert = 0x32
    KeyShare = 0x33
    NextProtocolNegotiation = 0x3374
    RenegotiationInfo = 0xff01
    EncryptedServerName = 0xffce


@unique
class ChangeCipherSpecType(IntEnum):
    ChangeCipherSpec = 1


@unique
class AlertLevel(IntEnum):
    Warn = 1
    Fatal = 2


@unique
class AlertDescription(IntEnum):
    CloseNotify = 0
    UnexpectedMessage = 10
    BadRecordMAC = 20
    DecryptionFailed = 21
    RecordOverflow = 22
    HandshakeFailure = 40
    NoCertificateReserved = 41
    BadCertificate = 42
    UnsupportedCertificate = 43
    CertificateRevoked = 44
    CertificateExpired = 45
    CertificateUnknown = 46
    IllegalParameter = 47
    UnknownCA = 48
    AccessDenied = 49
    DecodeError = 50
    DecryptError = 51
    ExportRestrictionReserved = 60
    ProtocolVersion = 70
    InsufficientSecurity = 71
    InternalError = 80
    InappropriateFallback = 86
    UserCanceled = 90
    NoRenegotiation = 100
    MissingExtension = 109
    UnsupportedExtension = 110
    CertificateUnobtainable = 111
    UnrecognizedName = 112
    BadCertificateStatusResponse = 113
    BadCertificateHashValue = 114
    UnknownPSKIdentity = 115
    CertificateRequired = 116
    NoApplicationProtocol = 120


@unique
class CipherSuite(IntEnum):
    AES_128_GCM_SHA256 = 0x1301
    AES_256_GCM_SHA384 = 0x1302
    CHACHA20_POLY1305_SHA256 = 0x1303
    AES_128_CCM_SHA256 = 0x1304
    AES_128_CCM_8_SHA256 = 0x1305


@unique
class SignatureAlgorithm(IntEnum):
    RSA_PKCS1_SHA1 = 0x0201
    ECDSA_SHA1 = 0x0203

    RSA_PKCS1_SHA256 = 0x0401
    RSA_PKCS1_SHA384 = 0x0501
    RSA_PKCS1_SHA512 = 0x0601

    ECDSA_SECP256R1_SHA256 = 0x0403
    ECDSA_SECP384R1_SHA384 = 0x0503
    ECDSA_SECP521R1_SHA512 = 0x0603

    RSA_PSS_RSAE_SHA256 = 0x0804
    RSA_PSS_RSAE_SHA384 = 0x0805
    RSA_PSS_RSAE_SHA512 = 0x0806

    ED25519 = 0x0807
    ED448 = 0x0808

    RSA_PSS_PSS_SHA256 = 0x0809
    RSA_PSS_PSS_SHA384 = 0x080a
    RSA_PSS_PSS_SHA512 = 0x080b


@unique
class NamedGroup(IntEnum):
    FFDHE2048 = 0x0100
    FFDHE3072 = 0x0101
    FFDHE4096 = 0x0102
    FFDHE6144 = 0x0103
    FFDHE8192 = 0x0104

    SECP256R1 = 0x0017
    SECP384R1 = 0x0018
    SECP521R1 = 0x0019

    X25519 = 0x001d
    X448 = 0x001e
