import asyncio
import socket
from abc import ABC, abstractmethod

from p3.contrib.basic.http import HTTPRequest, HTTPResponse
from p3.defaults import PING_TIMEOUT, PING_URL
from p3.iobox import Outbox, OutboxWrappedConnecotr
from p3.utils.override import override
from p3.utils.url import URL


class Ping(ABC):
    timeout: float
    url: URL

    def __init__(self, timeout: float = PING_TIMEOUT, url: str = PING_URL):
        self.timeout = timeout
        self.url = URL.from_str(url)
        if self.url.scheme not in ('http', ''):
            raise ValueError(f'invalid scheme {self.url.scheme}')
        if self.url.scheme == '':
            self.url.scheme = 'http'
        if self.url.port == 0:
            self.url.port = 80

    @abstractmethod
    def ping(self, outbox: Outbox):
        raise NotImplementedError


class TcpPing(Ping):

    @override(Ping)
    def ping(self, outbox: Outbox):
        with socket.create_connection(outbox.url.addr, timeout=self.timeout):
            pass


class ProxyPing(Ping):

    @override(Ping)
    def ping(self, outbox: Outbox):
        connector = OutboxWrappedConnecotr(outbox=outbox, addr=self.url.addr)
        req = HTTPRequest(method='GET', headers={'Host': self.url.host})

        async def test():
            stream = await connector.connect(rest=bytes(req))
            async with stream.cm():
                await HTTPResponse.read_from_stream(stream)

        async def main():
            await asyncio.wait_for(test(), timeout=self.timeout)

        asyncio.run(main())
