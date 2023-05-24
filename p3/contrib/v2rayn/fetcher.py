"""V2rayN format subscription fetcher.

Links:
  https://github.com/2dust/v2rayN/wiki/分享链接格式说明(ver-2)

* v: 配置文件版本号,主要用来识别当前配置
* ps: 备注或别名
* add: 地址IP或域名
* port: 端口号
* id: UUID
* aid: alterId
* scy: 加密方式(security),没有时值默认auto
* net: 传输协议(tcp,kcp,ws,h2,quic)
* type: 伪装类型(none,http,srtp,utp,wechat-video) *tcp or kcp or QUIC
* host: 伪装的域名

> 1. 1)http(tcp)->host中间逗号(,)隔开
> 1. 2)ws->host
> 1. 3)h2->host
> 1. 4)QUIC->securty

* path: path
> 1. 1)ws->path
> 1. 2)h2->path
> 1. 3)QUIC->key/Kcp->seed
> 1. 4)grpc->serviceName

* tls: 传输层安全(tls)
* sni: serverName
* alpn: `h2,http/1.1`
* fp: fingerprint

- Trans:
  ps        => name
  add:port  => url
  id        => userid
  net:tls   => net
  host:path => ws_host:ws_path
  sni:alpn  => tls_host:tls_protocols
- Ignores: aid, scy, fp
- Ensures: v=2, type=none
"""
import base64
import json
import re
from typing import Any

import requests

from p3.iobox import Fetcher, Outbox
from p3.utils.override import override
from p3.utils.url import URL


class V2rayNFetcher(Fetcher):
    scheme = 'v2rayn'

    URL_PATTERN = r'^([0-9a-zA-Z]+)://(.*)$'

    url_re = re.compile(URL_PATTERN)

    @override(Fetcher)
    def fetch(self) -> list[Outbox]:
        res = requests.get(self.url)
        if res.status_code != 200:
            res.raise_for_status()
        content = base64.decodebytes(res.content).decode()
        urls = content.split('\r\n')

        outboxes = list()
        for url in urls:
            try:
                url = url.strip()
                if len(url) == 0:
                    continue
                url_match = self.url_re.match(url)
                if url_match is None:
                    raise RuntimeError(f'invalid url: {url}')
                scheme = url_match[1]
                if scheme != 'vmess':
                    raise RuntimeError(f'invalid scheme: {scheme}')
                content = base64.decodebytes(url_match[2].encode()).decode()
                outboxes.append(self.parse_data(json.loads(content)))
            except Exception as e:
                self.logger.warning('except while fetching %s: %s', url, e)

        return outboxes

    def parse_data(self, data: Any) -> Outbox:
        v = data['v']
        if v != '2':
            raise RuntimeError(f'invalid v: {v}')
        dtype = data['type']
        if dtype != 'none':
            raise RuntimeError(f'invalid type: {dtype}')

        name: str = data['ps']
        host: str = data['add']
        port: int = data['port']
        userid: str = data['id']
        ws_host: str = data.get('host') or host
        ws_path: str = data.get('path') or '/'
        tls_host: str = data.get('sni') or host
        tls_protocols: str = data.get('alpn') or ''

        d = {'tcp:': 'tcp', 'tcp:tls': 'tls', 'ws:': 'ws', 'ws:tls': 'wss'}
        dnet = '{}:{}'.format(data['net'], data['tls'])
        net = d.get(dnet)
        if net is None:
            raise RuntimeError(f'invalid net: {dnet}')

        url = str(URL(scheme='vmess', host=host, port=port))

        return Outbox.from_dict({
            'scheme': 'vmess',
            'url': url,
            'name': name,
            'fetcher': self.name,
            'net': net,
            'ws_host': ws_host,
            'ws_path': ws_path,
            'tls_host': tls_host,
            'tls_protocols': tls_protocols,
            'userid': userid,
        })
