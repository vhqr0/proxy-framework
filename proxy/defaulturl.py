from yarl import URL

from .defaults import INBOX_URL, OUTBOX_URL


class DefaultURL:
    default: URL
    override: URL

    def __init__(self, url: str):
        self.override = URL(url)

    def __str__(self) -> str:
        url = URL.build(
            scheme=self.scheme,
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.pwd,
        )
        return str(url)

    @property
    def addr(self) -> tuple[str, int]:
        return self.host, self.port

    @property
    def scheme(self) -> str:
        return self.override.scheme or self.default.scheme or 'http'

    @property
    def host(self) -> str:
        return self.override.host or self.default.host or ''

    @property
    def port(self) -> int:
        return self.override.port or self.default.port or 0

    @property
    def user(self) -> str:
        return self.override.user or self.default.user or ''

    @property
    def pwd(self) -> str:
        return self.override.password or self.default.password or ''


class InboxDefaultURL(DefaultURL):
    default = URL(INBOX_URL)


class OutboxDefaultURL(DefaultURL):
    default = URL(OUTBOX_URL)
