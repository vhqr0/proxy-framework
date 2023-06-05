from enum import Enum, IntEnum, IntFlag
from typing import Any, Union

from typing_extensions import Self

from p3.stream.buffer import Buffer
from p3.stream.errors import ProtocolError
from p3.stream.stream import Stream
from p3.stream.structs import BaseStruct, BStruct, HStruct, IStruct


class BaseEnumMixin:
    scheme: str

    def raise_protocol_error(self):
        raise ProtocolError(self.scheme, str(self))

    def ensure(self, obj: Any):
        assert isinstance(self, Enum)
        obj = self.__class__(obj)
        if obj.value != self.value:
            obj.raise_protocol_error()


class BaseEnumProxyMeta(type):

    def __getattr__(self, name):
        return self(getattr(self.enum_type, name))


class BaseEnumProxy(BaseEnumMixin, metaclass=BaseEnumProxyMeta):
    enum_type: type[Enum]
    enum: Enum

    def __init__(self, enum):
        self.enum = self.enum_type(enum)

    def __str__(self) -> str:
        return str(self.enum)

    def __getattr__(self, name: str):
        return self.__class__(getattr(self.enum_type, name))

    @property
    def value(self):
        return self.enum.value


class BaseIntEnumMixin(BaseEnumMixin):
    struct: BaseStruct

    def __bytes__(self) -> bytes:
        assert isinstance(self, int)
        return self.pack(self)

    @classmethod
    def pack(cls, i: int) -> bytes:
        return cls.struct.pack(int(i))

    @classmethod
    async def read_from_stream(cls, stream: Stream) -> Self:
        i, = await cls.struct.read_from_stream(stream)
        assert issubclass(cls, int)
        return cls(i)

    @classmethod
    def pop_from_buffer(cls, buffer: Buffer) -> Self:
        i, = cls.struct.pop_from_buffer(buffer)
        assert issubclass(cls, int)
        return cls(i)

    @classmethod
    def get(cls, i: int) -> Union[Self, int]:
        assert issubclass(cls, int)
        try:
            return cls(i)
        except ValueError:
            return i


class BaseIntEnumProxy(BaseIntEnumMixin, BaseEnumProxy):

    def __int__(self) -> int:
        assert isinstance(self.enum, int)
        return int(self.enum)


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


# Bug of mypy, see: https://github.com/python/mypy/issues/9319
class BFlag(BEnumMixin, IntFlag):  # type: ignore
    pass


class HFlag(HEnumMixin, IntFlag):  # type: ignore
    pass


class IFlag(IEnumMixin, IntFlag):  # type: ignore
    pass
