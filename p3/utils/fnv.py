from struct import Struct

IStruct = Struct('!I')


def fnv32a(buf: bytes) -> bytes:
    r, p, m = 0x811c9dc5, 0x01000193, 0xffffffff
    for c in buf:
        r = ((r ^ c) * p) & m
    return IStruct.pack(r)
