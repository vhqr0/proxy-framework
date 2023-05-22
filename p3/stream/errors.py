import asyncio


class StreamError(Exception):
    pass


class ProtocolError(RuntimeError, StreamError):
    breadcrumb: list[str]
    protocol: str
    part: str

    def __init__(self, *breadcrumb: str):
        super().__init__('protocol error: ' + '/'.join(breadcrumb))
        self.breadcrumb = list(breadcrumb)


class BufferOverflowError(asyncio.LimitOverrunError, StreamError):

    def __init__(self, consumed: int = 0):
        super().__init__(message='buffer overflow', consumed=consumed)


class IncompleteReadError(asyncio.IncompleteReadError, StreamError):
    pass
