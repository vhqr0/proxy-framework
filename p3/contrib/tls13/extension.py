from abc import ABC, abstractmethod
from typing import Optional, Union
from enum import Enum, auto

from typing_extensions import Self

from p3.contrib.tls13.ciphers import (NamedGroup, NamedGroupList,
                                      SignatureSchemeList)
from p3.contrib.tls13.common import Version, VersionList, TLS13EnumMixin
from p3.stream.buffer import Buffer
from p3.stream.enums import HEnum
from p3.stream.structs import BaseStruct, HStruct
from p3.utils.override import override


class HandshakePhase(TLS13EnumMixin, Enum):
    CH = auto()
    SH = auto()
    EE = auto()
    CT = auto()
    CR = auto()
    NST = auto()
    HRR = auto()


class ExtensionType(HEnum):
    ServerName = 0
    MaxFragmentLength = 1
    StatusRequest = 5
    SupportedGroups = 10
    SignatureAlgorithms = 13
    UseSrtp = 14
    HeartBeat = 15
    ApplicationLayerProtocolNegotiation = 16
    SignedCertificateTimestamp = 18
    ClientCertificateType = 19
    ServerCertificateType = 20
    Padding = 21
    PreSharedKey = 41
    EarlyData = 42
    SupportedVersions = 43
    Cookie = 44
    PSKKeyExchangeModes = 45
    CertificateAuthorities = 47
    OidFilters = 48
    PostHandshakeAuth = 49
    SignatureAlgorithmsCert = 50
    KeyShare = 51


class Extension(ABC):
    extension_type: Union[ExtensionType, int]
    extension_dict: dict[int, type['Extension']] = dict()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'extension_type'):
            cls.extension_dict[int(cls.extension_type)] = cls

    def __bytes__(self) -> bytes:
        return HStruct.pack(int(self.extension_type)) + self.pack_extension()

    @abstractmethod
    def pack_extension(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def pop_from_buffer(
        cls,
        buffer: Buffer,
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        struct = ExtensionType.struct
        assert isinstance(struct, BaseStruct)
        extension_type, = struct.pop_from_buffer(buffer)
        extension_cls = cls.extension_dict.get(
            extension_type,
            UnknownExtension,
        )
        return extension_cls.pop_extension_from_buffer(
            buffer,
            extension_type,
            phase,
        )

    @classmethod
    @abstractmethod
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        raise NotImplementedError


class ExtensionList:
    extensions: list[Extension]

    def __init__(self, extensions: Optional[list[Extension]] = None):
        if extensions is None:
            extensions = list()
        self.extensions = extensions

    def __bytes__(self) -> bytes:
        buf = b''.join(bytes(extension) for extension in self.extensions)
        return HStruct.pack_varlen(buf)

    @classmethod
    def pop_from_buffer(
        cls,
        buffer: Buffer,
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> Self:
        buf = HStruct.pop_varlen_from_buffer(buffer)
        ebuffer = Buffer(buf)
        extensions = list()
        while len(ebuffer) != 0:
            extension = Extension.pop_from_buffer(buffer, phase)
            extensions.append(extension)
        return cls(extensions)


class UnknownExtension(Extension):
    extension_data: bytes

    def __init__(
        self,
        extension_type: Union[ExtensionType, int],
        extension_data: bytes,
    ):
        self.extension_type = extension_type
        self.extension_data = extension_data

    @override(Extension)
    def pack_extension(self) -> bytes:
        return HStruct.pack_varlen(self.extension_data)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        buf = HStruct.pop_varlen_from_buffer(buffer)
        return cls(extension_type, buf)


class SupportedVersions(Extension):
    versions: Union[Version, int, VersionList]

    extension_type = ExtensionType.SupportedVersions

    def __init__(self, versions: Union[Version, int, VersionList]):
        self.versions = versions

    @override(Extension)
    def pack_extension(self) -> bytes:
        if isinstance(self.versions, VersionList):
            return bytes(self.versions)
        else:
            return Version.pack(self.versions)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        if phase is HandshakePhase.CH:
            versions = VersionList.pop_from_buffer(buffer)
        elif phase is HandshakePhase.SH or phase is HandshakePhase.HRR:
            # mypy cannot recognize the type of Version.struct.
            struct = Version.struct
            assert isinstance(struct, BaseStruct)
            versions, = struct.pop_from_buffer_with_types(buffer, Version.get)
        else:
            raise cls.extension_type.raise_protocol_error()
        return cls(versions)


class Cookie(Extension):
    cookie: bytes

    extension_type = ExtensionType.Cookie

    def __init__(self, cookie: bytes):
        self.cookie = cookie

    @override(Extension)
    def pack_extension(self) -> bytes:
        return HStruct.pack_varlen(self.cookie)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        if phase is not HandshakePhase.CH and \
           phase is not HandshakePhase.HRR:
            cls.extension_type.raise_protocol_error()
        buf = HStruct.pop_varlen_from_buffer(buffer)
        return cls(buf)


class SignatureAlgorithms(Extension):
    algorithms: SignatureSchemeList

    extension_type = ExtensionType.SignatureAlgorithms

    def __init__(self, algorithms: Optional[SignatureSchemeList] = None):
        if algorithms is None:
            algorithms = SignatureSchemeList.defaults()
        self.algorithms = algorithms

    @override(Extension)
    def pack_extension(self) -> bytes:
        return bytes(self.algorithms)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        if phase is not HandshakePhase.CH and \
           phase is not HandshakePhase.CR:
            cls.extension_type.raise_protocol_error()
        algorithms = SignatureSchemeList.pop_from_buffer(buffer)
        return cls(algorithms)


class SupportedGroups(Extension):
    groups: NamedGroupList

    extension_type = ExtensionType.SupportedGroups

    def __init__(self, groups: Optional[NamedGroupList] = None):
        if groups is None:
            groups = NamedGroupList.defaults()
        self.groups = groups

    @override(Extension)
    def pack_extension(self) -> bytes:
        return bytes(self.groups)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        if phase is not HandshakePhase.CH and \
           phase is not HandshakePhase.EE:
            cls.extension_type.raise_protocol_error()
        groups = NamedGroupList.pop_from_buffer(buffer)
        return cls(groups)


class KeyShareEntry(ABC):
    group: Union[NamedGroup, int]

    def __bytes__(self) -> bytes:
        buf = self.pack_entry()
        return NamedGroup.pack(self.group) + HStruct.pack_varlen(buf)

    @abstractmethod
    def pack_entry(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def pop_from_buffer(cls, buffer: Buffer) -> 'KeyShareEntry':
        struct = NamedGroup.struct
        assert isinstance(struct, BaseStruct)
        group, = struct.pop_from_buffer_with_types(buffer, NamedGroup.get)
        if isinstance(group, NamedGroup):
            t = group & 0xff00
            if t == 0x0000:
                pass
            if t == 0x0100:
                pass
        return UnknownKeyShareEntry.pop_from_buffer(buffer)

    @classmethod
    @abstractmethod
    def pop_entry_from_buffer(cls, buffer: Buffer) -> 'KeyShareEntry':
        raise NotImplementedError


class UnknownKeyShareEntry(KeyShareEntry):
    key_exchange: bytes

    def __init__(self, key_exchange: bytes):
        self.key_exchange = key_exchange

    @override(KeyShareEntry)
    def pack_entry(self) -> bytes:
        return HStruct.pack_varlen(self.key_exchange)

    @classmethod
    @override(KeyShareEntry)
    def pop_from_buffer(cls, buffer: Buffer) -> 'KeyShareEntry':
        buf = HStruct.pop_varlen_from_buffer(buffer)
        return cls(buf)


class FFKeyShareEntry(KeyShareEntry):
    pass


class ECKeyShareEntry(KeyShareEntry):
    pass


class KeyShareEntryList:
    entries: list[KeyShareEntry]

    def __init__(self, entries: Optional[list[KeyShareEntry]] = None):
        if entries is None:
            entries = list()
        self.entries = entries

    def __bytes__(self) -> bytes:
        buf = b''.join(bytes(entry) for entry in self.entries)
        return HStruct.pack_varlen(buf)

    @classmethod
    def pop_from_buffer(cls, buffer: Buffer) -> Self:
        buf = HStruct.pop_varlen_from_buffer(buffer)
        ebuffer = Buffer(buf)
        entries = list()
        while len(ebuffer) != 0:
            entry = KeyShareEntry.pop_from_buffer(buffer)
            entries.append(entry)
        return cls(entries)


class KeyShare(Extension):
    entries: Union[KeyShareEntry, KeyShareEntryList, NamedGroup, int]

    extension_type = ExtensionType.KeyShare

    def __init__(
        self,
        entries: Union[KeyShareEntry, KeyShareEntryList, NamedGroup, int],
    ):
        self.entries = entries

    @override(Extension)
    def pack_extension(self) -> bytes:
        if isinstance(self.entries, (KeyShareEntry, KeyShareEntryList)):
            return bytes(self.entries)
        else:
            return NamedGroup.pack(self.entries)

    @classmethod
    @override(Extension)
    def pop_extension_from_buffer(
        cls,
        buffer: Buffer,
        extension_type: Union[ExtensionType, int],
        phase: HandshakePhase = HandshakePhase.CH,
    ) -> 'Extension':
        entries: Union[KeyShareEntry, KeyShareEntryList, NamedGroup, int]
        if phase is HandshakePhase.CH:
            entries = KeyShareEntryList.pop_from_buffer(buffer)
        elif phase is HandshakePhase.SH:
            entries = KeyShareEntry.pop_from_buffer(buffer)
        elif phase is HandshakePhase.HRR:
            struct = NamedGroup.struct
            assert isinstance(struct, BaseStruct)
            entries, = struct.pop_from_buffer_with_types(
                buffer, NamedGroup.get)
        else:
            cls.extension_type.raise_protocol_error()
        return cls(entries)
