import asyncio
from collections.abc import Coroutine
from typing import Any

from typing_extensions import Self

from p3.common.tcp import TCPAcceptor
from p3.iobox import Inbox
from p3.server.outdispatcher import Outdispatcher
from p3.utils.loggable import Loggable
from p3.utils.override import override
from p3.utils.serializable import SelfSerializable


class Server(SelfSerializable, Loggable):
    tasks: set[asyncio.Task]
    inbox: Inbox
    outdispatcher: Outdispatcher

    def __init__(self, inbox: Inbox, outdispatcher: Outdispatcher, **kwargs):
        super().__init__(**kwargs)
        self.tasks = set()
        self.inbox = inbox
        self.outdispatcher = outdispatcher

    @override(SelfSerializable)
    def to_dict(self) -> dict[str, Any]:
        return {
            'inbox': self.inbox.to_dict(),
            'outdispatcher': self.outdispatcher.to_dict(),
        }

    @classmethod
    @override(SelfSerializable)
    def from_dict(cls, obj: dict[str, Any]) -> Self:
        inbox = Inbox.from_dict(obj.get('inbox') or dict())
        outdispatcher = Outdispatcher.from_dict(
            obj.get('outdispatcher') or dict())
        return cls(inbox=inbox, outdispatcher=outdispatcher)

    def run(self):
        try:
            self.outdispatcher.rule_matcher.load_rules()
            self.outdispatcher.forward_outset.clean()
            asyncio.run(self.start_server())
        except Exception as e:
            self.logger.error('error while serving: %s', e)
            raise

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def start_server(self):
        server = await asyncio.start_server(
            self.connected_cb,
            self.inbox.url.host,
            self.inbox.url.port,
            reuse_address=True,
            **self.inbox.tcp_extra_kwargs,
        )
        addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
        self.logger.info('server start at %s', addrs)
        async with server:
            await server.serve_forever()

    def connected_cb(self, reader: asyncio.StreamReader,
                     writer: asyncio.StreamWriter):
        self.create_task(self.serve(reader, writer))

    async def serve(self, reader: asyncio.StreamReader,
                    writer: asyncio.StreamWriter):
        try:
            stream, req = await self.inbox.accept(
                next_acceptor=TCPAcceptor(reader, writer))
        except Exception as e:
            self.logger.debug('except while accepting: %.60s', e)
            return
        async with stream.cm() as s1:
            try:
                stream = await self.outdispatcher.connect(req)
            except Exception as e:
                self.logger.debug('except while connecting to %s: %.60s', req,
                                  e)
                return
            async with stream.cm() as s2:
                t1 = self.create_task(s1.write_stream(s2))
                t2 = self.create_task(s2.write_stream(s1))
                try:
                    await asyncio.gather(t1, t2)
                except Exception:
                    pass
                t1.cancel()
                t2.cancel()
