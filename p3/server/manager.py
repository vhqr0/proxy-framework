import argparse
import json
import logging
import os.path
from cmd import Cmd
from pprint import pprint
from typing import Optional

from p3.defaults import (BLOCK_OUTBOX_URL, CONFIG_FILE, CONNECT_ATTEMPTS,
                         DIRECT_OUTBOX_URL, INBOX_URL, LOG_DATE_FORMAT,
                         LOG_FORMAT, RULES_FALLBACK, RULES_FILE,
                         TLS_INBOX_CERT_FILE, TLS_INBOX_KEY_FILE,
                         TLS_INBOX_KEY_PWD, TLS_OUTBOX_CERT_FILE,
                         TLS_OUTBOX_HOST, TLS_OUTBOX_PROTOCOLS)
from p3.server.server import Server
from p3.utils.cmdwraps import cmdwraps
from p3.utils.loggable import Loggable


class Manager(Cmd, Loggable):
    config_file: str
    server: Server

    intro = 'Welcome to proxy cli. Type help or ? to list commands.\n'
    prompt = 'proxy cli $ '

    def __init__(self, config_file: str = CONFIG_FILE, **kwargs):
        super().__init__(**kwargs)
        self.config_file = config_file

    @property
    def outset(self):
        return self.server.outdispatcher.forward_outset

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
        parser.add_argument('-o',
                            '--forward-outbox-urls',
                            action='append',
                            default=list())
        parser.add_argument('--rules-fallback', default=RULES_FALLBACK)
        parser.add_argument('-r', '--rules-file', default=RULES_FILE)
        parser.add_argument('-A',
                            '--connect-attempts',
                            default=CONNECT_ATTEMPTS)
        parser.add_argument('-C',
                            '--tls-inbox-cert-file',
                            default=TLS_INBOX_CERT_FILE)
        parser.add_argument('-K',
                            '--tls-inbox-key-file',
                            default=TLS_INBOX_KEY_FILE)
        parser.add_argument('-p',
                            '--tls-inbox-key-pwd',
                            default=TLS_INBOX_KEY_PWD)
        parser.add_argument('-R',
                            '--tls-outbox-cert-file',
                            default=TLS_OUTBOX_CERT_FILE)
        parser.add_argument('-H', '--tls-outbox-host', default=TLS_OUTBOX_HOST)
        parser.add_argument('-P',
                            '--tls-outbox-protocols',
                            default=TLS_OUTBOX_PROTOCOLS)
        parser.add_argument('command', nargs=argparse.REMAINDER)
        args = parser.parse_args()

        logging.basicConfig(
            level='DEBUG' if args.debug else 'INFO',
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
        )

        manager = cls(config_file=args.config_file)
        if args.from_args:
            manager.load_from_args(args)
        else:
            manager.load()

        try:
            if args.command:
                manager.onecmd(' '.join(args.command))
            else:
                manager.cmdloop()
        except Exception as e:
            cls.logger.error('error while eval: %s', e)
        except KeyboardInterrupt:
            cls.logger.info('keyboard quit')

    def load_from_args(self, args: argparse.Namespace):
        inbox_url = args.inbox_url
        block_outbox_url = args.block_outbox_url
        direct_outbox_url = args.direct_outbox_url
        forward_outbox_urls = args.forward_outbox_urls
        tls_inbox_cert_file = args.tls_inbox_cert_file
        tls_inbox_key_file = args.tls_inbox_key_file
        tls_inbox_key_pwd = args.tls_inbox_key_pwd
        tls_outbox_cert_file = args.tls_outbox_cert_file
        tls_outbox_host = args.tls_outbox_host
        tls_outbox_protocols = args.tls_outbox_protocols
        rules_fallback = args.rules_fallback
        rules_file = args.rules_file
        connect_attempts = args.connect_attempts

        forward_outboxes = [{
            'url': url,
            'name': url,
            'tls_cert_file': tls_outbox_cert_file,
            'tls_host': tls_outbox_host,
            'tls_protocols': tls_outbox_protocols,
        } for url in forward_outbox_urls]

        obj = {
            'inbox': {
                'url': inbox_url,
                'tls_cert_file': tls_inbox_cert_file,
                'tls_key_file': tls_inbox_key_file,
                'tls_key_pwd': tls_inbox_key_pwd,
            },
            'outdispatcher': {
                'rule_matcher': {
                    'rules_fallback': rules_fallback,
                    'rules_file': rules_file,
                },
                'block_outbox': {
                    'url': block_outbox_url,
                    'name': 'BLOCK',
                    'tls_cert_file': tls_outbox_cert_file,
                    'tls_host': tls_outbox_host,
                    'tls_protocols': tls_outbox_protocols,
                },
                'direct_outbox': {
                    'url': direct_outbox_url,
                    'name': 'DIRECT',
                    'tls_cert_file': tls_outbox_cert_file,
                    'tls_host': tls_outbox_host,
                    'tls_protocols': tls_outbox_protocols,
                },
                'forward_outset': {
                    'outboxes': forward_outboxes,
                    'connect_attempts': connect_attempts,
                },
            }
        }

        self.server = Server.from_dict(obj)

    def load(self, config_file: Optional[str] = None):
        if config_file is None:
            config_file = self.config_file
        if os.path.exists(config_file):
            with open(config_file) as f:
                obj = json.load(f)
        else:
            self.logger.warning('cannot find config file: %s', config_file)
            obj = dict()
        self.server = Server.from_dict(obj)
        self.logger.debug('load %d outboxes', len(self.outset.outboxes))

    def dump(self, config_file: Optional[str] = None):
        if config_file is None:
            config_file = self.config_file
        with open(config_file, 'w') as f:
            json.dump(self.server.to_dict(), f)

    def do_EOF(self, args: str):
        raise KeyboardInterrupt

    @cmdwraps([(['config_file'], {'nargs': '?'})])
    def do_dump(self, args: argparse.Namespace):
        if args.config_file == '-':
            pprint(self.server.to_dict())
        else:
            self.dump(args.config_file or self.config_file)

    @cmdwraps([(['idxes'], {'nargs': argparse.REMAINDER, 'type': int})])
    def do_rm(self, args: argparse.Namespace):
        if args.idxes:
            self.outset.select(args.idxes, invert=True)
            self.dump()

    @cmdwraps([(['idxes'], {'nargs': argparse.REMAINDER, 'type': int})])
    def do_run(self, args: argparse.Namespace):
        if args.idxes:
            self.outset.select(args.idxes)
        self.server.run()

    @cmdwraps([(['idxes'], {'nargs': argparse.REMAINDER, 'type': int})])
    def do_ls(self, args: argparse.Namespace):
        if args.idxes:
            self.outset.select(args.idxes)
        self.outset.ls()

    @cmdwraps([(['idxes'], {'nargs': argparse.REMAINDER, 'type': int})])
    def do_ping(self, args: argparse.Namespace):
        if args.idxes:
            self.outset.select(args.idxes)
        self.outset.ping()
        self.dump()

    @cmdwraps([(['names'], {'nargs': argparse.REMAINDER})])
    def do_fetch(self, args: argparse.Namespace):
        if args.names:
            self.outset.fetch(args.names)
        else:
            self.outset.fetch()
        self.dump()
