from typing import Any

from .common import override, MappedSerializable, Loggable
from .outbox import Outbox


class Fetcher(MappedSerializable['Fetcher'], Loggable):
    url: str
    name: str

    scheme_map = dict()

    def __init__(self, url: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.name = name

    def __str__(self) -> str:
        return f'<{self.scheme}://{self.name}>'

    @override(MappedSerializable)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['url'] = self.url
        obj['name'] = self.name
        return obj

    @classmethod
    @override(MappedSerializable)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['url'] = obj['url']
        kwargs['name'] = obj['name']
        return kwargs

    def fetch(self) -> list[Outbox]:
        raise NotImplementedError
