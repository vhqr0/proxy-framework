from proxy.iobox import Outbox
from proxy.stream import Connector, ProxyRequest, Stream
from proxy.utils.override import override


class NULLStream(Stream):

    @override(Stream)
    def write_primitive(self, buf: bytes):
        pass

    @override(Stream)
    async def read_primitive(self) -> bytes:
        return b''


class NULLConnector(Connector):

    @override(Connector)
    async def connect(self, rest: bytes = b'') -> Stream:
        return NULLStream()


class NULLOutbox(Outbox):
    scheme = 'null'
    ping_skip = True

    @override(Outbox)
    async def connect(self, req: ProxyRequest) -> Stream:
        connector = NULLConnector()
        return await connector.connect(rest=req.rest)


class BlockOutbox(NULLOutbox):
    scheme = 'block'
