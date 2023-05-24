import random
from typing import Any, Optional

from typing_extensions import Self

from p3.defaults import (WEIGHT_DECREASE_STEP, WEIGHT_INCREASE_STEP,
                         WEIGHT_INITIAL, WEIGHT_MAXIMAL, WEIGHT_MINIMAL)
from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import DispatchedSerializable


class Weight:
    _weight: float

    def __init__(self, weight: float = WEIGHT_INITIAL):
        self._weight = weight

    @property
    def val(self) -> float:
        return self._weight

    def __str__(self) -> str:
        return '{:.2f}W'.format(self._weight)

    def __repr__(self) -> str:
        return 'Weight({})'.format(self._weight)

    def increase(self):
        self._weight = min(self._weight + WEIGHT_INCREASE_STEP, WEIGHT_MAXIMAL)

    def decrease(self):
        self._weight = max(self._weight - WEIGHT_DECREASE_STEP, WEIGHT_MINIMAL)

    def reset(self):
        self._weight = WEIGHT_INITIAL

    def disable(self):
        self._weight = -1.0

    def disabled(self) -> bool:
        return self._weight <= 0

    def enabled(self) -> bool:
        return not self.disabled()


class Weightable(Loggable):
    weight: Weight

    def __init__(self, weight: Optional[Weight] = None, **kwargs):
        super().__init__(**kwargs)
        if weight is None:
            weight = Weight()
        self.weight = weight

    @override(DispatchedSerializable)
    def to_dict(self) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        obj = super().to_dict()  # type: ignore
        obj['weight'] = self.weight.val
        return obj

    @classmethod
    @override(DispatchedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        # Virtual inherit from DispatchedSerializable.
        kwargs = super().kwargs_from_dict(obj)  # type: ignore
        weight = obj.get('weight')
        if weight is not None:
            kwargs['weight'] = Weight(weight)
        return kwargs

    @classmethod
    def choices_by_weight(cls, population: list[Self], k: int) -> list[Self]:
        weights = [i.weight.val for i in population]
        return random.choices(population, weights=weights, k=k)
