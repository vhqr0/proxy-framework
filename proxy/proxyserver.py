import asyncio
from typing import Any, Optional

from .common import Loggable, Serializable, override
from .inbox import Inbox
from .outboxdispatcher import OutboxDispatcher
from .stream import Stream


class ProxyServer(Serializable['ProxyServer'], Loggable):
    tasks: set[asyncio.Task]
    inbox: Inbox
    outbox_dispatcher: OutboxDispatcher

    def __init__(self, inbox: Inbox, outbox_dispatcher: OutboxDispatcher,
                 **kwargs):
        super().__init__(**kwargs)
        self.tasks = set()
        self.inbox = inbox
        self.outbox_dispatcher = outbox_dispatcher

    @override(Serializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'inbox': self.inbox.to_dict(),
            'outbox_dispatcher': self.outbox_dispatcher.to_dict(),
        }

    @classmethod
    @override(Serializable)
    def from_dict(cls, obj: dict[str, Any]) -> 'ProxyServer':
        inbox = Inbox.from_dict(obj.get('inbox') or dict())
        outbox_dispatcher = OutboxDispatcher.from_dict(
            obj.get('outbox_dispatcher') or dict())
        return cls(inbox=inbox, outbox_dispatcher=outbox_dispatcher)

    def run(self):
        try:
            self.outbox_dispatcher.rule_matcher.load_rules()
            asyncio.run(self.start_server())
        except Exception as e:
            self.logger.error('error while serving: %s', e)
            raise

    async def start_server(self):
        server = await asyncio.start_server(
            self.open_connection,
            self.inbox.url.host,
            self.inbox.url.port,
            reuse_address=True,
            **self.inbox.tcp_extra_kwargs,
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        self.logger.info('server start at %s', addrs)
        async with server:
            await server.serve_forever()

    async def open_connection(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        try:
            req = await self.inbox.accept_from_tcp(reader, writer)
            outboxes = self.outbox_dispatcher.dispatch(req.addr[0])
        except Exception as e:
            self.logger.debug('except while accepting: %.60s', e)
            return

        for retry, outbox in enumerate(outboxes):
            try:
                self.logger.info('connect to %s via %s retry %d', req, outbox,
                                 retry)
                stream = await outbox.connect(req=req)
                break
            except Exception as e:
                outbox.weight_decrease()
                self.logger.debug(
                    'except while connecting to %s via %s retry %d: %.60s',
                    req, outbox, retry, e)
        else:
            self.logger.debug('except while reconnecting to %s', req)
            try:
                req.stream.close()
                await req.stream.wait_closed()
            except Exception:
                pass
            return

        try:
            await self.stream_proxy(req.stream, stream)
            outbox.weight_increase()
        except Exception as e:
            outbox.weight_decrease()
            self.logger.debug('except while proxing to %s via %s: %.60s', req,
                              outbox, e)

    async def stream_proxy(self, s1: Stream, s2: Stream):
        tasks = (
            asyncio.create_task(s1.write_stream(s2)),
            asyncio.create_task(s2.write_stream(s1)),
        )
        for task in tasks:
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

        exc: Optional[Exception] = None

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            exc = e
            for task in tasks:
                if not task.cancelled():
                    task.cancel()

        for s in (s1, s2):
            try:
                s.close()
                await s.wait_closed()
            except Exception as e:
                if exc is None:
                    exc = e

        if exc is not None:
            raise exc
