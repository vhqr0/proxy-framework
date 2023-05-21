import ssl
from typing import Any

from proxy.defaults import (TLS_INBOX_CERT_FILE, TLS_INBOX_KEY_FILE,
                            TLS_INBOX_KEY_PWD, TLS_OUTBOX_CERT_FILE,
                            TLS_OUTBOX_HOST)
from proxy.iobox.inbox import Inbox
from proxy.iobox.outbox import Outbox
from proxy.utils.override import override


class TLSCtxInbox(Inbox):
    tls_cert_file: str
    tls_key_file: str
    tls_key_pwd: str
    tls_ctx: ssl.SSLContext

    def __init__(self,
                 tls_cert_file: str = TLS_INBOX_CERT_FILE,
                 tls_key_file: str = TLS_INBOX_KEY_FILE,
                 tls_key_pwd: str = TLS_INBOX_KEY_PWD,
                 **kwargs):
        super().__init__(**kwargs)
        self.tls_cert_file = tls_cert_file
        self.tls_key_file = tls_key_file
        self.tls_key_pwd = tls_key_pwd
        self.tls_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.tls_ctx.load_cert_chain(
            certfile=self.tls_cert_file,
            keyfile=self.tls_key_file,
            password=self.tls_key_pwd or None,
        )
        self.tcp_extra_kwargs['ssl'] = self.tls_ctx

    @override(Inbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['tls_cert_file'] = self.tls_cert_file
        obj['tls_key_file'] = self.tls_key_file
        obj['tls_key_pwd'] = self.tls_key_pwd
        return obj

    @classmethod
    @override(Inbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['tls_cert_file'] = obj.get('tls_cert_file') or \
            TLS_INBOX_CERT_FILE
        kwargs['tls_key_file'] = obj.get('tls_key_file') or TLS_INBOX_KEY_FILE
        kwargs['tls_key_pwd'] = obj.get('tls_key_pwd') or TLS_INBOX_KEY_PWD
        return kwargs


class TLSCtxOutbox(Outbox):
    tls_cert_file: str
    tls_host: str
    tls_ctx: ssl.SSLContext

    def __init__(self,
                 tls_cert_file: str = TLS_OUTBOX_CERT_FILE,
                 tls_host: str = TLS_OUTBOX_HOST,
                 **kwargs):
        super().__init__(**kwargs)
        self.tls_cert_file = tls_cert_file
        self.tls_host = tls_host
        self.tls_ctx = ssl.create_default_context(
            cafile=self.tls_cert_file or None)
        self.tcp_extra_kwargs['ssl'] = self.tls_ctx
        self.tcp_extra_kwargs['server_hostname'] = self.tls_host

    @override(Outbox)
    def to_dict(self) -> dict[str, Any]:
        obj = super().to_dict()
        obj['tls_cert_file'] = self.tls_cert_file
        obj['tls_host'] = self.tls_host
        return obj

    @classmethod
    @override(Outbox)
    def kwargs_from_dict(cls, obj: dict[str, Any]) -> dict[str, Any]:
        kwargs = super().kwargs_from_dict(obj)
        kwargs['tls_cert_file'] = obj.get('tls_cert_file') or \
            TLS_OUTBOX_CERT_FILE
        kwargs['tls_host'] = obj.get('tls_host') or TLS_OUTBOX_HOST
        return kwargs
