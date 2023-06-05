from enum import Enum
from typing import Union

from typing_extensions import Self

from p3.stream.buffer import Buffer
from p3.stream.enums import BaseEnumMixin, BaseIntEnumMixin, BEnum, HEnum
from p3.stream.structs import BaseStruct, BStruct


class TLS13EnumMixin(BaseEnumMixin):
    scheme = 'tls13'


class TLS13IntEnumMixin(TLS13EnumMixin, BaseIntEnumMixin):
    pass


class TLS13BEnum(TLS13IntEnumMixin, BEnum):
    pass


class TLS13HEnum(TLS13IntEnumMixin, HEnum):
    pass


class Version(TLS13HEnum):
    SSL30 = 0x0300
    TLS10 = 0x0301
    TLS11 = 0x0302
    TLS12 = 0x0303
    TLS13 = 0x0304


class TLS13IntEnumList:
    struct: BaseStruct
    enum_type: type[TLS13IntEnumMixin]
    enums: list[Union[TLS13IntEnumMixin, int]]

    def __init__(self, enums: list[Union[TLS13IntEnumMixin, int]]):
        self.enums = enums

    def __bytes__(self):
        enums = list()
        for enum in self.enums:
            assert isinstance(enum, int)
            enums.append(int(enum))
        buf = b''.join(self.enum_type.pack(enum) for enum in enums)
        return self.struct.pack_varlen(buf)

    @classmethod
    def pop_from_buffer(cls, buffer: Buffer) -> Self:
        buf = cls.struct.pop_varlen_from_buffer(buffer)
        ebuffer = Buffer(buf)
        enums: list[Union[TLS13IntEnumMixin, int]] = list()
        while len(ebuffer) != 0:
            enum, = cls.enum_type.struct.pop_from_buffer_with_types(
                buffer, cls.enum_type.get)
            enums.append(enum)
        return cls(enums)

    @classmethod
    def defaults(cls) -> Self:
        assert issubclass(cls.enum_type, Enum)
        return cls(list(cls.enum_type))


class VersionList(TLS13IntEnumList):
    struct = BStruct
    enum_type = Version
