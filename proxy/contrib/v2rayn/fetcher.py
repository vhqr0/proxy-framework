"""V2rayN format subscription fetcher.

Links:
  https://github.com/2dust/v2rayN/wiki/分享链接格式说明(ver-2)
"""
import base64
import json
import re
from typing import Any

import requests

from proxy.iobox import Fetcher, Outbox
from proxy.utils.override import override
from proxy.utils.url import URL


class V2rayNFetcher(Fetcher):
    scheme = 'v2rayn'

    URL_PATTERN = r'^([0-9a-zA-Z]+)://(.*)$'

    url_re = re.compile(URL_PATTERN)

    net_dict: dict[str, str] = {
        'tcp+': 'tcp',
        'tcp+tls': 'tls',
        'ws+': 'ws',
        'ws+tls': 'wss',
    }

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
        dtype: str = data['type']
        dnet: str = '{}+{}'.format(data['net'], data['tls'])
        host: str = data['add']
        port: int = data['port']
        name: str = data['ps']
        ws_path: str = data.get('path') or '/'
        ws_host: str = data.get('host') or host
        tls_host: str = data.get('sni') or host
        userid: str = data['id']

        if dtype != 'none':
            raise RuntimeError(f'invalid type: {dtype}')

        net = self.net_dict.get(dnet)
        if net is None:
            raise RuntimeError(f'invalid net: {dnet}')

        url = str(URL(scheme='vmess', host=host, port=port))

        return Outbox.from_dict({
            'scheme': 'vmess',
            'url': url,
            'name': name,
            'fetcher': self.name,
            'net': net,
            'ws_path': ws_path,
            'ws_host': ws_host,
            'tls_host': tls_host,
            'userid': userid,
        })
