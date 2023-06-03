from enum import Enum, IntEnum, IntFlag
from struct import Struct

from typing_extensions import Self

from p3.stream.errors import ProtocolError
from p3.stream.stream import Stream
from p3.stream.structs import BStruct, HStruct, IStruct


class BaseEnumMixin:
    scheme: str

    def raise_from_scheme(self):
        raise ProtocolError(self.scheme, str(self))

    def ensure(self, obj):
        obj = self.__class__(obj)  # type: ignore
        if obj.value != self.value:  # type: ignore
            obj.raise_from_scheme()


class BaseEnumProxyMeta(type):

    def __getattr__(self, name):
        return self(getattr(self.enumType, name))


class BaseEnumProxy(BaseEnumMixin, metaclass=BaseEnumProxyMeta):
    enumType: type[Enum]
    enum: Enum

    def __init__(self, enum):
        self.enum = self.enumType(enum)

    def __str__(self) -> str:
        return str(self.enum)

    def __getattr__(self, name: str):
        return self.__class__(getattr(self.enumType, name))

    @property
    def value(self):
        return self.enum.value


class BaseIntEnumMixin(BaseEnumMixin):
    struct: Struct

    def __bytes__(self) -> bytes:
        return self.struct.pack(int(self))  # type: ignore

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        i, = await stream.read_struct(cls.struct)
        return cls(i)  # type: ignore


class BaseIntEnumProxy(BaseIntEnumMixin, BaseEnumProxy):

    def __int__(self) -> int:
        return int(self.enum)  # type: ignore


class BEnumMixin(BaseIntEnumMixin):
    struct = BStruct


class HEnumMixin(BaseIntEnumMixin):
    struct = HStruct


class IEnumMixin(BaseIntEnumMixin):
    struct = IStruct


class BEnum(BEnumMixin, IntEnum):
    pass


class HEnum(HEnumMixin, IntEnum):
    pass


class IEnum(IEnumMixin, IntEnum):
    pass


class BFlag(BEnumMixin, IntFlag):  # type: ignore
    pass


class HFlag(HEnumMixin, IntFlag):  # type: ignore
    pass


class IFlag(IEnumMixin, IntFlag):  # type: ignore
    pass
