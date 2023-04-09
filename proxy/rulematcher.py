import os.path
from enum import Enum, auto
from functools import cache
from typing import Any, Optional

from typing_extensions import Self

from .common import Loggable, SelfSerializable, override
from .defaults import RULES_DEFAULT, RULES_FILE


class Rule(Enum):
    Block = auto()
    Direct = auto()
    Forward = auto()

    @classmethod
    def from_str(cls, s: str) -> Self:
        s = s.lower()
        if s == 'block':
            return cls(cls.Block)
        if s == 'direct':
            return cls(cls.Direct)
        if s == 'forward':
            return cls(cls.Forward)
        raise ValueError


class RuleMatcher(SelfSerializable, Loggable):
    rules_default: Rule
    rules_file: str
    rules: Optional[dict[str, Rule]]

    def __init__(self,
                 rules_default: str = RULES_DEFAULT,
                 rules_file: str = RULES_FILE,
                 **kwargs):
        super().__init__(**kwargs)
        self.rules_default = Rule.from_str(rules_default)
        self.rules_file = rules_file
        self.rules = None

    @override(SelfSerializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'rules_default': str(self.rules_default),
            'rules_file': self.rules_file,
        }

    @classmethod
    @override(SelfSerializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        return cls(rules_default=obj.get('rules_default') or RULES_DEFAULT,
                   rules_file=obj.get('rules_file') or RULES_FILE)

    def load_rules(self, force: bool = False):
        if not force and self.rules is not None:
            return
        if len(self.rules_file) == 0:
            self.logger.info('skip load rules file')
            return
        if not os.path.exists(self.rules_file):
            self.logger.info('cannot find rules file')
            return
        self.rules = dict()
        with open(self.rules_file) as f:
            for line in f:
                line = line.strip()
                if len(line) == 0 or line[0] == '#':
                    continue
                try:
                    rule, domain = line.split(maxsplit=1)
                    if domain not in self.rules:
                        self.rules[domain] = Rule.from_str(rule)
                except Exception as e:
                    self.logger.warning('except while loading rule %s: %s',
                                        line, e)
        self.logger.info('load %d rules', len(self.rules))

    @cache
    def match(self, domain: str) -> Rule:
        if self.rules is None:
            return self.rules_default
        rule = self.rules.get(domain)
        if rule is not None:
            return rule
        sp = domain.split('.', 1)
        if len(sp) > 1:
            return self.match(sp[1])
        return self.rules_default
