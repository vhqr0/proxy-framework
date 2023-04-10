import argparse
import json
import logging
import os.path
from cmd import Cmd
from concurrent.futures import ThreadPoolExecutor
from pprint import pprint
from typing import Optional

from .common import Loggable
from .defaults import (BLOCK_OUTBOX_URL, CONFIG_FILE, CONNECT_RETRY,
                       DIRECT_OUTBOX_URL, INBOX_URL, LOG_DATE_FORMAT,
                       LOG_FORMAT, RULES_DEFAULT, RULES_FILE,
                       TLS_INBOX_CERT_FILE, TLS_INBOX_KEY_FILE,
                       TLS_INBOX_KEY_PWD, TLS_OUTBOX_CERT_FILE,
                       TLS_OUTBOX_HOST)
from .outbox import Outbox
from .proxyserver import ProxyServer


class Manager(Cmd, Loggable):
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
        parser.add_argument('-B',
                            '--block-outbox-url',
                            default=BLOCK_OUTBOX_URL)
        parser.add_argument('-O',
                            '--direct-outbox-url',
                            default=DIRECT_OUTBOX_URL)
        parser.add_argument('-o', '--forward-outbox-urls', action='append')
        parser.add_argument('-D', '--rules-default', default=RULES_DEFAULT)
        parser.add_argument('-F', '--rules-file', default=RULES_FILE)
        parser.add_argument('-r', '--connect-retry', default=CONNECT_RETRY)
        parser.add_argument('-C',
                            '--tls-inbox-cert-file',
                            default=TLS_INBOX_CERT_FILE)
        parser.add_argument('-K',
                            '--tls-inbox-key-file',
                            default=TLS_INBOX_KEY_FILE)
        parser.add_argument('-P',
                            '--tls-inbox-key-pwd',
                            default=TLS_INBOX_KEY_PWD)
        parser.add_argument('-R',
                            '--tls-outbox-cert-file',
                            default=TLS_OUTBOX_CERT_FILE)
        parser.add_argument('-H', '--tls-outbox-host', default=TLS_OUTBOX_HOST)
        parser.add_argument('command', nargs=argparse.REMAINDER)
        args = parser.parse_args()

        debug = args.debug
        from_args = args.from_args
        config_file = args.config_file
        command = args.command

        logging.basicConfig(
            level='DEBUG' if debug else 'INFO',
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
        )

        manager = cls(config_file=config_file)
        if from_args:
            manager.load_from_args(args)
        else:
            manager.load()

        try:
            if command is None or len(command) == 0:
                manager.cmdloop()
            else:
                manager.onecmd(' '.join(command))
        except Exception as e:
            cls.logger.error('error while eval: %s', e)
        except KeyboardInterrupt:
            cls.logger.info('keyboard quit')

    def load_from_args(self, args: argparse.Namespace):
        inbox_url = args.inbox_url
        block_outbox_url = args.block_outbox_url
        direct_outbox_url = args.direct_outbox_url
        forward_outbox_urls = args.forward_outbox_urls or list()
        tls_inbox_cert_file = args.tls_inbox_cert_file
        tls_inbox_key_file = args.tls_inbox_key_file
        tls_inbox_key_pwd = args.tls_inbox_key_pwd
        tls_outbox_cert_file = args.tls_outbox_cert_file
        tls_outbox_host = args.tls_outbox_host
        rules_default = args.rules_default
        rules_file = args.rules_file
        connect_retry = args.connect_retry

        forward_outboxes = [{
            'url': url,
            'name': url,
            'tls_cert_file': tls_outbox_cert_file,
            'tls_host': tls_outbox_host,
        } for url in forward_outbox_urls]

        obj = {
            'inbox': {
                'url': inbox_url,
                'tls_cert_file': tls_inbox_cert_file,
                'tls_key_file': tls_inbox_key_file,
                'tls_key_pwd': tls_inbox_key_pwd,
            },
            'outbox_dispatcher': {
                'rule_matcher': {
                    'rules_default': rules_default,
                    'rules_file': rules_file,
                },
                'block_outbox': {
                    'url': block_outbox_url,
                    'name': 'BLOCK',
                    'tls_cert_file': tls_outbox_cert_file,
                    'tls_host': tls_outbox_host,
                },
                'direct_outbox': {
                    'url': direct_outbox_url,
                    'name': 'DIRECT',
                    'tls_cert_file': tls_outbox_cert_file,
                    'tls_host': tls_outbox_host,
                },
                'forward_outboxes': forward_outboxes,
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
            pprint(self.proxy_server.to_dict())
        else:
            self.dump(args or self.config_file)

    def do_run(self, args: str):
        outboxes = self.outboxes(args)
        self.proxy_server.outbox_dispatcher.forward_outboxes = outboxes
        self.proxy_server.run()

    def do_ls(self, args: str):
        outboxes = self.outboxes(args)
        for idx, outbox in enumerate(outboxes):
            print(f'{idx}\t{outbox.summary()}')

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

    def do_fetch(self, args: str):
        fetchers = self.proxy_server.outbox_dispatcher.fetchers
        fetcher_names = args.split()
        if len(fetcher_names) != 0:
            fetchers = [
                fetcher for fetcher in fetchers
                if fetcher.name in fetcher_names
            ]
        for fetcher in fetchers:
            outboxes = fetcher.fetch()
            for outbox in self.proxy_server.outbox_dispatcher.forward_outboxes:
                if outbox.fetcher != fetcher.name:
                    outboxes.append(outbox)
            self.proxy_server.outbox_dispatcher.forward_outboxes = outboxes
        self.dump()
