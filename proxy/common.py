import logging

from typing_extensions import Self
from typing import TypeVar, Generic, Any, Optional
from collections.abc import Callable

Meth = TypeVar('Meth')


# Links:
#   https://stackoverflow.com/questions/1167617/in-python-how-do-i-indicate-im-overriding-a-method
#   https://github.com/mkorpela/overrides
def override(cls: Any) -> Callable[[Meth], Meth]:
    """Check for overrides without losing type hints."""

    def override(meth: Meth) -> Meth:
        assert getattr(meth, '__name__') in dir(cls), \
            'override check failed'
        return meth

    return override


class Loggable:
    """Auto add logger based on class name."""

    logger: logging.Logger

    def __init_subclass__(cls, **kwargs):
        cls.logger = logging.getLogger(cls.__name__)

    def __init__(self, **kwargs):
        for k in kwargs:
            self.logger.warning('unused kwarg: %s', k)


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        raise NotImplementedError


Layer = TypeVar('Layer')


class MultiLayer(Generic[Layer], Loggable):
    next_layer: Optional[Layer]

    ensure_next_layer: bool = False

    def __init__(self, next_layer: Optional[Layer] = None, **kwargs):
        super().__init__(**kwargs)
        if self.ensure_next_layer and next_layer is None:
            raise TypeError('next_layer cannot be None')
        self.next_layer = next_layer
