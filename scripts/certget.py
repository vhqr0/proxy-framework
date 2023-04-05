#!/usr/bin/env python3
"""Get cert from trojan server.

Copy from https://github.com/trojan-gfw/trojan [/scripts/getcert.py].
"""

import argparse
import socket
import ssl

from yarl import URL

parser = argparse.ArgumentParser()
parser.add_argument('url', type=URL)
args = parser.parse_args()

url = args.url
host = url.host or 'localhost'
port = url.port or 443
addr = (host, port)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
with socket.create_connection(addr) as sock:
    with ctx.wrap_socket(sock) as ssock:
        print(ssl.DER_cert_to_PEM_cert(ssock.getpeercert(True)), end='')
