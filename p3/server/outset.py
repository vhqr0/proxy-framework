from typing import Any, Optional

from typing_extensions import Self

from p3.common.tcp import DirectOutbox
from p3.defaults import CONNECT_ATTEMPTS, PING_TIMEOUT, PING_URL
from p3.iobox import Fetcher, Outbox
from p3.server.ping import Ping, ProxyPing, TcpPing
from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import SelfSerializable


class Outset(SelfSerializable, Loggable):
    outboxes: list[Outbox]
    fetchers: list[Fetcher]
    connect_attempts: int

    def __init__(
        self,
        outboxes: Optional[list[Outbox]] = None,
        fetchers: Optional[list[Fetcher]] = None,
        connect_attempts: int = CONNECT_ATTEMPTS,
        **kwargs,
    ):
        super().__init__(**kwargs)
        if outboxes is None:
            outboxes = list()
        if fetchers is None:
            fetchers = list()
        self.outboxes = outboxes
        self.fetchers = fetchers
        self.connect_attempts = connect_attempts

    @override(SelfSerializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'outboxes': [outbox.to_dict() for outbox in self.outboxes],
            'fetchers': [fetcher.to_dict() for fetcher in self.fetchers],
            'connect_attempts': self.connect_attempts,
        }

    @classmethod
    @override(SelfSerializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        outboxes = list()
        for outbox_obj in obj.get('outboxes') or list():
            outboxes.append(Outbox.from_dict(outbox_obj))
        fetchers = list()
        for fetcher_obj in obj.get('fetchers') or list():
            fetchers.append(Fetcher.from_dict(fetcher_obj))
        connect_attempts = obj.get('connect_attempts') or CONNECT_ATTEMPTS
        return cls(
            outboxes=outboxes,
            fetchers=fetchers,
            connect_attempts=connect_attempts,
        )

    def clean(self):
        self.outboxes = [
            outbox for outbox in self.outboxes if outbox.weight.enabled()
        ]
        if len(self.outboxes) == 0:
            self.logger.warning('auto add forward outbox')
            self.outboxes.append(DirectOutbox(name='FORWARD'))
        self.connect_attempts = min(self.connect_attempts, len(self.outboxes))

    def choices(self):
        return Outbox.choices_by_weight(self.outboxes, k=self.connect_attempts)

    def select(self, idxes: list[int], invert: bool = False):
        outboxes = []
        for idx, outbox in enumerate(self.outboxes):
            collect = idx in idxes
            if invert:
                collect = not collect
            if collect:
                outboxes.append(outbox)
        self.outboxes = outboxes

    def ls(self):
        Outbox.ls_all(self.outboxes)

    def ping(
        self,
        level: str = 'proxy',
        timeout: float = PING_TIMEOUT,
        url: str = PING_URL,
        verbose: bool = False,
    ):
        ping_cls: type[Ping]
        if level == 'proxy':
            ping_cls = ProxyPing
        elif level == 'tcp':
            ping_cls = TcpPing
        else:
            raise ValueError(f'invalid level: {level}')
        Outbox.ping_all(
            self.outboxes,
            ping_cls(timeout=timeout, url=url).ping,
            verbose=verbose,
        )

    def fetch(self, names: Optional[list[str]] = None):
        for fetcher in self.fetchers:
            if names is None or fetcher.name in names:
                try:
                    outboxes = fetcher.fetch()
                    for outbox in self.outboxes:
                        if outbox.name != fetcher.name:
                            outboxes.append(outbox)
                    self.outboxes = outboxes
                except Exception as e:
                    self.logger.error('error while fetcing %s: %s', fetcher, e)
