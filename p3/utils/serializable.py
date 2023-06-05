from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from typing_extensions import Self

from p3.utils.override import override


class Serializable(ABC):

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, obj: dict[str, Any]) -> Any:
        raise NotImplementedError


class SelfSerializable(Serializable, ABC):

    @classmethod
    @abstractmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        raise NotImplementedError


Scheme = TypeVar('Scheme')


class DispatchedSerializable(Generic[Scheme], Serializable):
    scheme: str
    scheme_dict: dict[str, type[Scheme]]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'scheme_dict'):
            cls.scheme_dict = dict()
        if hasattr(cls, 'scheme'):
            cls.scheme_dict[cls.scheme] = cls

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {'scheme': self.scheme}

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> Scheme:
        scheme = cls.scheme_from_dict(obj)
        scheme_cls = cls.scheme_dict[scheme]
        kwargs = scheme_cls.kwargs_from_dict(obj)
        return scheme_cls(**kwargs)

    @classmethod
    def scheme_from_dict(cls, obj: dict[str, Any]) -> str:
        return obj['scheme']

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        return dict()
