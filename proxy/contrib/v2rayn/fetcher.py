"""V2rayN format subscription fetcher.

Links:
  https://github.com/2dust/v2rayN/wiki/分享链接格式说明(ver-2)
"""
import re
import base64
import json

from yarl import URL
import requests

from proxy.common import override
from proxy.outbox import Outbox
from proxy.fetcher import Fetcher


class V2rayNFetcher(Fetcher):
    scheme = 'v2rayn'

    url_re = re.compile('^([0-9a-zA-Z]+)://(.*)$')

    @override(Fetcher)
    def fetch(self) -> list[Outbox]:
        res = requests.get(self.url)
        if res.status_code != 200:
            res.raise_for_status()
        content = base64.decodebytes(res.content).decode()
        urls = content.split('\r\n')

        outboxes = list()
        for url in urls:
            url_match = self.url_re.match(url)
            if url_match is None or url_match[1] != 'vmess':
                continue
            content = base64.decodebytes(url_match[2].encode()).decode()
            data = json.loads(content)
            if data['net'] != 'tcp':
                continue
            url = str(
                URL.build(
                    scheme='vmess',
                    host=data['add'],
                    port=data['port'],
                ))
            outboxes.append(
                Outbox.from_dict({
                    'scheme': 'vmess',
                    'url': url,
                    'name': data['ps'],
                    'fetcher': self.name,
                    'userid': data['id'],
                }))

        return outboxes
