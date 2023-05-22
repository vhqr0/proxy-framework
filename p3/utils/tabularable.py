from abc import ABC, abstractmethod

from typing_extensions import Self


class Tabularable(ABC):

    @abstractmethod
    def summary(self) -> str:
        raise NotImplementedError

    @classmethod
    def ls_all(cls, objs: list[Self]):
        n = len(str(len(objs)))
        f = '{:%d} | {}' % n
        for idx, obj in enumerate(objs):
            print(f.format(idx, obj.summary()))
