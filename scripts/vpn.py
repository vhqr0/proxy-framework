#!/usr/bin/env python3
"""Encrypted VPN.

```
ip tuntap add dev tun0 mode tun
ip l set tun0 up
ip l set tun0 mtu 1400
ip a add 10.0.1.1/30 dev tun0
echo 1 > /proc/sys/net/ipv6/conf/tun0/disable_ipv6

# connect
./vpn.py -l vpn://:<pwd1>@localhost:1080 -p vpn://:<pwd2>@localhost:1081

# accept
./vpn.py -l vpn://:<pwd2>@localhost:1081 -p vpn://:<pwd1>@localhost:1080 -a
```

The two nodes can both connect to each other, or one node accept the
peer's connection.
"""

import argparse
import array
import fcntl
import hashlib
import logging
import os
import platform
import random
import socket
import struct
import threading
import time
from typing import Union
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CTR

TUNPATH = '/dev/net/tun'
TUNIFNAME = 'tun0'
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000
IFF_PERSIST = 0x0800
IFNAMSIZE = 16
IFREQSIZE = {'32bit': 32, '64bit': 40}[platform.architecture()[0]]


def open_tun(name: str, flags: int) -> int:
    ifname = array.array('B', name.encode()[:IFNAMSIZE - 1])
    ifreq = array.array('B', bytes(IFREQSIZE))
    ifreq[:len(ifname)] = ifname
    ifreq[16:18] = array.array('B', struct.pack('@H', flags))
    tun = os.open(TUNPATH, os.O_RDWR)
    fcntl.ioctl(tun, TUNSETIFF, ifreq)
    return tun


LOCAL_URL = 'vpn://localhost:1080'
LOCAL_ADDR = 'localhost'
LOCAL_PORT = 1080
PEER_URL = 'vpn://localhost:1081'
PEER_ADDR = 'localhost'
PEER_PORT = 1081
PEER_VALIDTIME = 30
MSG_VALIDTIME = 5
LOG_FORMAT = '%(asctime)s %(name)s %(levelname)s %(message)s'
LOG_DATEFMT = '%y-%m-%d %H:%M:%S'


class VPN:
    key: bytes
    peer_key: bytes

    tun: int
    sock: socket.socket

    peer_addrport: tuple[str, int]
    peer_dynamic_accept: bool
    peer_ts: int
    peer_seq: int

    peer_validtime: int
    msg_validtime: int

    logger = logging.getLogger('vpn')

    def __init__(self,
                 key: Union[str, bytes],
                 peer_key: Union[str, bytes],
                 tun_ifname: str = TUNIFNAME,
                 local_addr: str = LOCAL_ADDR,
                 local_port: int = LOCAL_PORT,
                 peer_addr: str = PEER_ADDR,
                 peer_port: int = PEER_PORT,
                 peer_dynamic_accept: bool = False,
                 peer_validtime: int = PEER_VALIDTIME,
                 msg_validtime: int = MSG_VALIDTIME):
        if isinstance(key, str):
            key = hashlib.md5(key.encode()).digest()
        self.key = key
        if isinstance(peer_key, str):
            peer_key = hashlib.md5(peer_key.encode()).digest()
        self.peer_key = peer_key
        self.tun = open_tun(tun_ifname, IFF_TUN)
        addrinfo = socket.getaddrinfo(
            local_addr,
            local_port,
            type=socket.SOCK_DGRAM,
        )
        family, _, _, _, res = random.choice(addrinfo)
        addrport = res[0], res[1]
        self.sock = socket.socket(family, socket.SOCK_DGRAM)
        self.sock.bind(addrport)
        addrinfo = socket.getaddrinfo(
            peer_addr,
            peer_port,
            family=family,
            type=socket.SOCK_DGRAM,
        )
        _, _, _, _, res = random.choice(addrinfo)
        self.peer_addrport = res[0], res[1]
        self.peer_dynamic_accept = peer_dynamic_accept
        self.peer_ts = -1
        self.peer_seq = -1
        self.peer_validtime = peer_validtime
        self.msg_validtime = msg_validtime

    def run(self):
        self.logger.info('peer addr %s', self.peer_addrport)
        recver = threading.Thread(target=self.recver, daemon=True)
        recver.start()
        self.sender()

    def sender(self):
        try:
            aes = AES(self.key)
            seq = random.getrandbits(31)
            while True:
                buf = os.read(self.tun, 4096)
                seq = (seq + 1) & 0xffffffff
                ts = int(time.time()) & 0xffffffff
                if self.peer_dynamic_accept and \
                   abs(ts - self.peer_ts) > self.peer_validtime:
                    self.logger.debug('send give up for peer')
                    continue
                self.logger.debug('send %d bytes', len(buf))
                buf = struct.pack('!II', ts, seq) + buf
                iv = random.randbytes(16)
                cipher = Cipher(aes, CTR(iv))
                encryptor = cipher.encryptor()
                buf = iv + encryptor.update(buf) + encryptor.finalize()
                self.sock.sendto(buf, self.peer_addrport)
        except Exception as e:
            self.logger.error('error while sending: %s', e)
            exit(-1)

    def recver(self):
        try:
            aes = AES(self.peer_key)
            while True:
                buf, res = self.sock.recvfrom(4096)
                addrport = res[0], res[1]
                if not self.peer_dynamic_accept and \
                   addrport != self.peer_addrport:
                    continue
                try:
                    iv, buf = buf[:16], buf[16:]
                    cipher = Cipher(aes, CTR(iv))
                    decryptor = cipher.decryptor()
                    buf = decryptor.update(buf) + decryptor.finalize()
                    ts, seq = struct.unpack_from('!II', buffer=buf, offset=0)
                    buf = buf[8:]
                    now = int(time.time()) & 0xffffffff
                    if abs(now - ts) > self.msg_validtime or \
                       ts < self.peer_ts or \
                       (ts == self.peer_ts and seq <= self.peer_seq):
                        self.logger.debug('recv give up for msg')
                        continue
                    self.peer_ts, self.peer_seq = ts, seq
                    if self.peer_dynamic_accept and \
                       addrport != self.peer_addrport:
                        self.peer_addrport = addrport
                        self.logger.info('dynamic accept from %s', addrport)
                except Exception as e:
                    self.logger.warning('except while recving: %s', e)
                self.logger.debug('recv %d bytes', len(buf))
                os.write(self.tun, buf)
        except Exception as e:
            self.logger.error('error while recving: %s', e)
            exit(-1)

    @classmethod
    def main(cls):
        parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--debug', action='store_true')
        parser.add_argument('-l', '--local-url', default=LOCAL_URL)
        parser.add_argument('-p', '--peer-url', default=PEER_URL)
        parser.add_argument('-i', '--tun-ifname', default=TUNIFNAME)
        parser.add_argument('-a', '--dynamic-accept', action='store_true')
        parser.add_argument('--peer-validtime',
                            type=int,
                            default=PEER_VALIDTIME)
        parser.add_argument('--msg-validtime', type=int, default=MSG_VALIDTIME)
        args = parser.parse_args()

        debug = args.debug
        local_url = urlparse(args.local_url)
        local_addr = local_url.hostname or LOCAL_ADDR
        local_port = local_url.port or LOCAL_PORT
        password = local_url.password
        peer_url = urlparse(args.peer_url)
        peer_addr = peer_url.hostname or PEER_ADDR
        peer_port = peer_url.port or PEER_PORT
        peer_password = peer_url.password
        tun_ifname = args.tun_ifname
        dynamic_accept = args.dynamic_accept
        peer_validtime = args.peer_validtime
        msg_validtime = args.msg_validtime

        logging.basicConfig(level='DEBUG' if debug else 'INFO',
                            format=LOG_FORMAT,
                            datefmt=LOG_DATEFMT)

        vpn = cls(key=password,
                  peer_key=peer_password,
                  tun_ifname=tun_ifname,
                  local_addr=local_addr,
                  local_port=local_port,
                  peer_addr=peer_addr,
                  peer_port=peer_port,
                  peer_dynamic_accept=dynamic_accept,
                  peer_validtime=peer_validtime,
                  msg_validtime=msg_validtime)

        try:
            vpn.run()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    VPN.main()
