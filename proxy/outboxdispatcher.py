import random

from typing_extensions import Self
from typing import Any, Optional

from .defaults import CONNECT_RETRY
from .common import override, Serializable, Loggable
from .rulematcher import Rule, RuleMatcher
from .outbox import Outbox, NULLOutbox, TCPOutbox


class OutboxDispatcher(Serializable, Loggable):
    rule_matcher: RuleMatcher
    block_outbox: NULLOutbox
    direct_outbox: TCPOutbox
    forward_outboxes: list[Outbox]
    connect_retry: int

    def __init__(self,
                 rule_matcher: RuleMatcher,
                 outboxes: Optional[list[Outbox]],
                 connect_retry: int = CONNECT_RETRY):
        self.rule_matcher = rule_matcher
        self.block_outbox = NULLOutbox(name='BLOCK')
        self.direct_outbox = TCPOutbox(name='DIRECT')
        if outboxes is None or len(outboxes) == 0:
            outboxes = [TCPOutbox(name='FORWARD')]
            self.logger.warning('auto add forward outbox')
        self.forward_outboxes = outboxes
        self.connect_retry = connect_retry

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'rule_matcher': self.rule_matcher.to_dict(),
            'outboxes': [outbox.to_dict() for outbox in self.forward_outboxes],
            'connect_retry': self.connect_retry,
        }

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        rule_matcher = RuleMatcher.from_dict(obj.get('rule_matcher') or dict())
        outboxes = []
        for outbox_obj in obj.get('outboxes') or []:
            outboxes.append(Outbox.from_dict(outbox_obj))
        connect_retry = obj.get('connect_retry') or CONNECT_RETRY
        return cls(rule_matcher=rule_matcher,
                   outboxes=outboxes,
                   connect_retry=connect_retry)

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
            k=min(self.connect_retry, len(self.forward_outboxes)),
        )
