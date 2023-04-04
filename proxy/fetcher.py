from typing import Any

from .common import override, Serializable, Loggable
from .outbox import Outbox


class Fetcher(Serializable, Loggable):
    scheme: str
    url: str
    name: str

    scheme_dict: dict[str, type['Fetcher']] = dict()

    def __init__(self, url: str, name: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.name = name

    def __init_subclass__(cls, **kwargs):
        if hasattr(cls, 'scheme'):
            cls.scheme_dict[cls.scheme] = cls

    def __str__(self) -> str:
        return f'<{self.scheme}://{self.name}>'

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {'scheme': self.scheme, 'url': self.url, 'name': self.name}

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'Fetcher':
        fetcher_cls = cls.scheme_dict[obj['scheme']]
        kwargs = fetcher_cls.kwargs_from_dict(obj)
        return fetcher_cls(**kwargs)

    @classmethod
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = {'url': obj['url'], 'name': obj['name']}
        return kwargs

    def fetch(self) -> list[Outbox]:
        raise NotImplementedError
