from typing import Generic, Optional, TypeVar

from p3.utils.loggable import Loggable

Layer = TypeVar('Layer')


class Layerable(Generic[Layer], Loggable):
    next_layer: Optional[Layer]

    ensure_next_layer: bool = False

    def __init__(self, next_layer: Optional[Layer] = None, **kwargs):
        super().__init__(**kwargs)
        if self.ensure_next_layer and next_layer is None:
            raise ValueError('next_layer cannot be none')
        self.next_layer = next_layer
