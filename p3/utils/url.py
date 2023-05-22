from typing import Any, Optional

from typing_extensions import Self
from yarl import URL as yaURL


class URL:
    scheme: str
    host: str
    port: int
    user: str
    pwd: str

    def __init__(
        self,
        scheme: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        pwd: Optional[str] = None,
        fallback: Optional[Self] = None,
    ):
        if scheme:
            self.scheme = scheme
        elif fallback and fallback.scheme:
            self.scheme = fallback.scheme
        else:
            self.scheme = ''

        if host:
            self.host = host
        elif fallback and fallback.host:
            self.host = fallback.host
        else:
            self.host = ''

        if port:
            self.port = port
        elif fallback and fallback.port:
            self.port = fallback.port
        else:
            self.port = 0

        if user:
            self.user = user
        elif fallback and fallback.user:
            self.user = fallback.user
        else:
            self.user = ''

        if pwd:
            self.pwd = pwd
        elif fallback and fallback.pwd:
            self.pwd = fallback.pwd
        else:
            self.pwd = ''

    def __str__(self) -> str:
        kwargs: dict[str, Any] = dict()
        if self.scheme:
            kwargs['scheme'] = self.scheme
        if self.host:
            kwargs['host'] = self.host
        if self.port:
            kwargs['port'] = self.port
        if self.user:
            kwargs['user'] = self.user
        if self.pwd:
            kwargs['password'] = self.pwd
        yaurl = yaURL.build(**kwargs)
        return str(yaurl)

    def __repr__(self) -> str:
        return 'URL.from_str({})'.format(repr(str(self)))

    @property
    def addr(self) -> tuple[str, int]:
        return self.host, self.port

    @classmethod
    def from_str(cls, s: str, fallback: Optional[Self] = None) -> Self:
        yaurl = yaURL(s)
        scheme = yaurl.scheme or None
        host = yaurl.host or None
        # Use explicit port to avoid default by scheme.
        # Comment to skip this line while type checking.
        port = yaurl.explicit_port or None  # type: ignore
        user = yaurl.user or None
        pwd = yaurl.password or None
        return cls(
            scheme=scheme,
            host=host,
            port=port,
            user=user,
            pwd=pwd,
            fallback=fallback,
        )
