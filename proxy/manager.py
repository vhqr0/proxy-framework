import os.path
from concurrent.futures import ThreadPoolExecutor
import json
import pprint
import cmd
import logging
import argparse

from typing import Optional

from .defaults import (
    CONFIG_FILE,
    INBOX_URL,
    RULES_DEFAULT,
    RULES_FILE,
    CONNECT_RETRY,
    LOG_FORMAT,
    LOG_DATEFMT,
)
from .common import Loggable
from .outbox import Outbox
from .proxyserver import ProxyServer


class Manager(cmd.Cmd, Loggable):
    config_file: str
    proxy_server: ProxyServer

    intro = 'Welcome to proxy cli. Type help or ? to list commands.\n'
    prompt = 'proxy cli $ '

    def __init__(self, config_file: str = CONFIG_FILE, **kwargs):
        super().__init__(**kwargs)
        self.config_file = config_file

    @classmethod
    def main(cls, **kwargs):
        parser = argparse.ArgumentParser(**kwargs)
        parser.add_argument('-d', '--debug', action='store_true')
        parser.add_argument('-a', '--from-args', action='store_true')
        parser.add_argument('-c', '--config-file', default=CONFIG_FILE)
        parser.add_argument('-i', '--inbox-url', default=INBOX_URL)
        parser.add_argument('-o', '--outbox-urls', action='append', default=[])
        parser.add_argument('-D', '--rules-default', default=RULES_DEFAULT)
        parser.add_argument('-F', '--rules-file', default=RULES_FILE)
        parser.add_argument('-r', '--connect-retry', default=CONNECT_RETRY)
        parser.add_argument('command', nargs=argparse.REMAINDER)
        args = parser.parse_args()

        debug = args.debug
        from_args = args.from_args
        config_file = args.config_file
        command = args.command

        logging.basicConfig(
            level='DEBUG' if debug else 'INFO',
            format=LOG_FORMAT,
            datefmt=LOG_DATEFMT,
        )

        try:
            manager = cls(config_file=config_file)
            if from_args:
                manager.load_from_args(args)
            else:
                manager.load()
            if command is None or len(command) == 0:
                manager.cmdloop()
            else:
                manager.onecmd(' '.join(command))
        except Exception as e:
            cls.logger.error('error while eval: %s', e)
            raise
        except KeyboardInterrupt:
            pass

    def load_from_args(self, args: argparse.Namespace):
        inbox_url = args.inbox_url
        outbox_urls = args.outbox_urls
        rules_default = args.rules_default
        rules_file = args.rules_file
        connect_retry = args.connect_retry

        outboxes = [{'url': url, 'name': url} for url in outbox_urls]
        obj = {
            'inbox': {
                'url': inbox_url,
            },
            'outbox_dispatcher': {
                'rule_matcher': {
                    'rules_default': rules_default,
                    'rules_file': rules_file,
                },
                'outboxes': outboxes,
                'country_retry': connect_retry,
            }
        }

        self.proxy_server = ProxyServer.from_dict(obj)

    def load(self, config_file: Optional[str] = None):
        if config_file is None:
            config_file = self.config_file
        if os.path.exists(config_file):
            with open(config_file) as f:
                obj = json.load(f)
        else:
            obj = dict()
        self.proxy_server = ProxyServer.from_dict(obj)

    def dump(self, config_file: Optional[str] = None):
        if config_file is None:
            config_file = self.config_file
        with open(config_file, 'w') as f:
            json.dump(self.proxy_server.to_dict(), f)

    def outboxes(self, args: str, inverse: bool = False) -> list[Outbox]:
        outboxes = self.proxy_server.outbox_dispatcher.forward_outboxes
        idxes = [int(idx) for idx in args.split()]
        idxes = [idx for idx in idxes if 0 <= idx < len(outboxes)]
        if len(idxes) == 0:
            idxes = list(range(len(outboxes)))
        if inverse:
            idxes = [idx for idx in range(len(outboxes)) if idx not in idxes]
        outboxes = [outboxes[idx] for idx in idxes]
        return outboxes

    def do_EOF(self, args: str):
        raise KeyboardInterrupt

    def do_dump(self, args: str):
        args = args.strip()
        if args == '-':
            pprint.pprint(self.proxy_server.to_dict())
        else:
            self.dump(args)

    def do_run(self, args: str):
        outboxes = self.outboxes(args)
        self.proxy_server.outbox_dispatcher.forward_outboxes = outboxes
        self.proxy_server.run()

    def do_ls(self, args: str):
        outboxes = self.outboxes(args)
        for outbox in outboxes:
            print(outbox.summary())

    def do_rm(self, args: str):
        outboxes = self.outboxes(args, inverse=True)
        self.proxy_server.outbox_dispatcher.forward_outboxes = outboxes
        self.dump()

    def do_ping(self, args: str):

        def ping(outbox: Outbox):
            outbox.ping()
            print(outbox.summary())

        outboxes = self.outboxes(args)
        with ThreadPoolExecutor() as executor:
            executor.map(ping, outboxes)
        self.dump()
