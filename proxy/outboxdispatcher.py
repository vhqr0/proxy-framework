import random
from typing import Any, Optional

from typing_extensions import Self

from .common import Loggable, SelfSerializable, override
from .defaults import CONNECT_RETRY
from .fetcher import Fetcher
from .outbox import NULLOutbox, Outbox, TCPOutbox
from .request import Request
from .rulematcher import Rule, RuleMatcher
from .stream import Stream


class OutboxDispatcher(SelfSerializable, Loggable):
    rule_matcher: RuleMatcher
    block_outbox: Outbox
    direct_outbox: Outbox
    forward_outboxes: list[Outbox]
    fetchers: list[Fetcher]
    connect_retry: int

    def __init__(self,
                 rule_matcher: RuleMatcher,
                 block_outbox: Optional[Outbox] = None,
                 direct_outbox: Optional[Outbox] = None,
                 forward_outboxes: Optional[list[Outbox]] = None,
                 fetchers: Optional[list[Fetcher]] = None,
                 connect_retry: int = CONNECT_RETRY,
                 **kwargs):
        super().__init__(**kwargs)
        self.rule_matcher = rule_matcher
        self.block_outbox = block_outbox \
            if block_outbox is not None else NULLOutbox(name='BLOCK')
        self.direct_outbox = direct_outbox \
            if direct_outbox is not None else TCPOutbox(name='DIRECT')
        self.forward_outboxes = forward_outboxes \
            if forward_outboxes is not None else list()
        self.fetchers = fetchers if fetchers is not None else list()
        self.connect_retry = connect_retry

    def check_outboxes(self):
        self.forward_outboxes = [
            outbox for outbox in self.forward_outboxes if outbox.weight > 0.0
        ]
        if len(self.forward_outboxes) == 0:
            self.logger.warning('auto add forward outbox')
            self.forward_outboxes.append(TCPOutbox(name='FORWARD'))
        self.connect_retry = \
            min(self.connect_retry, len(self.forward_outboxes))

    @override(SelfSerializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'rule_matcher':
            self.rule_matcher.to_dict(),
            'block_outbox':
            self.block_outbox.to_dict(),
            'direct_outbox':
            self.direct_outbox.to_dict(),
            'forward_outboxes':
            [outbox.to_dict() for outbox in self.forward_outboxes],
            'fetchers': [fetcher.to_dict() for fetcher in self.fetchers],
            'connect_retry':
            self.connect_retry,
        }

    @classmethod
    @override(SelfSerializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        rule_matcher = RuleMatcher.from_dict(obj.get('rule_matcher') or dict())
        outbox_obj = obj.get('block_outbox')
        block_outbox = Outbox.from_dict(outbox_obj) \
            if outbox_obj is not None else None
        outbox_obj = obj.get('direct_outbox')
        direct_outbox = Outbox.from_dict(outbox_obj) \
            if outbox_obj is not None else None
        forward_outboxes = list()
        for outbox_obj in obj.get('forward_outboxes') or list():
            forward_outboxes.append(Outbox.from_dict(outbox_obj))
        fetchers = list()
        for fetcher_obj in obj.get('fetchers') or list():
            fetchers.append(Fetcher.from_dict(fetcher_obj))
        connect_retry = obj.get('connect_retry') or CONNECT_RETRY
        return cls(
            rule_matcher=rule_matcher,
            block_outbox=block_outbox,
            direct_outbox=direct_outbox,
            forward_outboxes=forward_outboxes,
            fetchers=fetchers,
            connect_retry=connect_retry,
        )

    def dispatch(self, addr: str) -> list[Outbox]:
        rule = self.rule_matcher.match(addr)
        if rule == Rule.Block:
            return [self.block_outbox]
        if rule == Rule.Direct:
            return [self.direct_outbox]
        weights = [outbox.weight for outbox in self.forward_outboxes]
        return random.choices(
            self.forward_outboxes,
            weights=weights,
            k=self.connect_retry,
        )

    async def connect(self, req: Request) -> Stream:
        for retry, outbox in enumerate(self.dispatch(req.addr[0])):
            self.logger.info('connect(%d) to %s via %s', retry, req, outbox)
            try:
                stream = await outbox.connect(req=req)
                outbox.weight_increase()
                return stream
            except Exception as e:
                outbox.weight_decrease()
                self.logger.debug('connect(%d) to %s via %s: %.60s', retry,
                                  req, outbox, e)
        raise RuntimeError('connect retry exceeded')
