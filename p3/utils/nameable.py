from typing import Any, Optional

from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import DispatchedSerializable


class Nameable(Loggable):
    name: str

    def __init__(self, name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        if name is None:
            name = self.__class__.__name__
        self.name = name

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        assert isinstance(self, DispatchedSerializable)
        obj = super().to_dict()
        obj['name'] = self.name
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        assert issubclass(cls, DispatchedSerializable)
        kwargs = super().kwargs_from_dict(obj)
        kwargs['name'] = obj.get('name') or cls.__name__
        return kwargs
