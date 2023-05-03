import random

from typing_extensions import Self

from ..common import Loggable
from ..defaults import (WEIGHT_DECREASE_STEP, WEIGHT_INCREASE_STEP,
                        WEIGHT_INITIAL, WEIGHT_MAXIMAL, WEIGHT_MINIMAL)


class Weightable(Loggable):
    weight: float

    def __init__(self, weight: float = WEIGHT_INITIAL, **kwargs):
        super().__init__(**kwargs)
        self.weight = weight

    def weight_increase(self):
        self.weight = min(self.weight + WEIGHT_INCREASE_STEP, WEIGHT_MAXIMAL)

    def weight_decrease(self):
        self.weight = max(self.weight - WEIGHT_DECREASE_STEP, WEIGHT_MINIMAL)

    @classmethod
    def choices_by_weight(cls, population: list[Self], k: int) -> list[Self]:
        weights = [i.weight for i in population]
        return random.choices(population, weights=weights, k=k)
