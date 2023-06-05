from p3.stream.errors import BufferOverflowError


class Buffer:
    buf: bytes
    blen: int
    bcur: int

    def __init__(self, buf: bytes):
        self.buf = buf
        self.blen = len(self.buf)
        self.bcur = 0

    def __bytes__(self) -> bytes:
        return self.buf[self.bcur:]

    def __len__(self) -> int:
        return self.blen

    def pop(self, n: int) -> bytes:
        if n > self.blen:
            self.bcur += self.blen
            self.blen = 0
            raise BufferOverflowError(self.blen)
        buf = self.buf[self.bcur:self.bcur + n]
        self.bcur += n
        self.blen -= n
        return buf
