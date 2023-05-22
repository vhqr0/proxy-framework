# P3: Python Proxy Platform

P3 is a python proxy platform, as well as a general protocol library,
which includes:

## `p3.stream`

A multi layer `stream` abstraction on top of `asyncio`, as well as
`acceptor` and `connector` to open a stream actively or passively.

## `p3.iobox`

Abstracting serializable proxy configuration of acceptor and connector
to `inbox` and `outbox`, and `fetcher` to fetch `outbox` from a proxy
server feed.

## `p3.server`

A rule based, dynamically directional, auto reconnecting proxy server
implementation, while providing an easy to use command line interface,
see `python3 -m p3.server -h` for more details.

## `p3.contrib`

Some protocols implementations that shipped with `p3`, including:

### `p3.contrib.basic`

- Stream Protocols: `ws`
- Proxy Protocols: `socks5`, `http`, `trojan`

### `p3.contrib.v2rayn`

- Proxy Protocols: `vmess`
- Fetcher Protocols: `v2rayn`

TODO:

- Proxy Protocols: `ss`

### `p3.contrib.tls13`

PS. A asyncio based python level `tls` implementation.

TODO:

- Stream Protocols: `tls13`

### `p3.contrib.ssh`

TODO:

- Stream Protocols: `ssh`
