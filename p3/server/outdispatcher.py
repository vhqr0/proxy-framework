from typing import Any, Optional

from typing_extensions import Self

from p3.common.null import BlockOutbox
from p3.common.tcp import DirectOutbox
from p3.iobox import Outbox
from p3.server.outset import Outset
from p3.server.rulematcher import Rule, RuleMatcher
from p3.stream import ProxyRequest, Stream
from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import SelfSerializable


class Outdispatcher(SelfSerializable, Loggable):
    rule_matcher: RuleMatcher
    block_outbox: Outbox
    direct_outbox: Outbox
    forward_outset: Outset

    def __init__(
        self,
        rule_matcher: RuleMatcher,
        block_outbox: Optional[Outbox] = None,
        direct_outbox: Optional[Outbox] = None,
        forward_outset: Optional[Outset] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.rule_matcher = rule_matcher
        self.block_outbox = block_outbox or BlockOutbox(name='BLOCK')
        self.direct_outbox = direct_outbox or DirectOutbox(name='DIRECT')
        self.forward_outset = forward_outset or Outset()

    @override(SelfSerializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'rule_matcher': self.rule_matcher.to_dict(),
            'block_outbox': self.block_outbox.to_dict(),
            'direct_outbox': self.direct_outbox.to_dict(),
            'forward_outset': self.forward_outset.to_dict(),
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
        outset_obj = obj.get('forward_outset')
        forward_outset = Outset.from_dict(outset_obj) \
            if outset_obj is not None else None
        return cls(
            rule_matcher=rule_matcher,
            block_outbox=block_outbox,
            direct_outbox=direct_outbox,
            forward_outset=forward_outset,
        )

    def dispatch(self, addr: str) -> list[Outbox]:
        rule = self.rule_matcher.match(addr)
        if rule == Rule.Block:
            return [self.block_outbox]
        if rule == Rule.Direct:
            return [self.direct_outbox]
        return self.forward_outset.choices()

    async def connect(self, req: ProxyRequest) -> Stream:
        for retry, outbox in enumerate(self.dispatch(req.addr[0])):
            self.logger.info('connect(%d) to %s via %s', retry, req, outbox)
            try:
                stream = await outbox.connect(req=req)
                outbox.weight.increase()
                return stream
            except Exception as e:
                outbox.weight.decrease()
                self.logger.debug('connect(%d) to %s via %s: %.60s', retry,
                                  req, outbox, e)
        raise RuntimeError('connect retry exceeded')
