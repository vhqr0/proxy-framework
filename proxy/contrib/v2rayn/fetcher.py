"""V2rayN format subscription fetcher.

Links:
  https://github.com/2dust/v2rayN/wiki/分享链接格式说明(ver-2)
"""
import base64
import json
import re

import requests
from yarl import URL

from proxy.common import override
from proxy.server import Fetcher, Outbox


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
                url_match = self.url_re.match(url)
                if url_match is None:
                    self.logger.warning('invalid url: %s', url)
                    continue
                if url_match[1] != 'vmess':
                    self.logger.warning('invalid scheme: %s', url_match[1])
                    continue
                content = base64.decodebytes(url_match[2].encode()).decode()
                data = json.loads(content)
                if data['type'] != 'none':
                    self.logger.warning('invalid type: %s', data['type'])
                    continue
                if data['net'] == 'tcp' and data['tls'] == '':
                    net = 'tcp'
                elif data['net'] == 'tcp' and data['tls'] == 'tls':
                    net = 'tls'
                elif data['net'] == 'ws' and data['tls'] == '':
                    net = 'ws'
                elif data['net'] == 'ws' and data['tls'] == 'tls':
                    net = 'wss'
                else:
                    self.logger.warning('invalid net: %s %s', data['net'],
                                        data['tls'])
                    continue
                outboxes.append(
                    Outbox.from_dict({
                        'scheme':
                        'vmess',
                        'url':
                        str(
                            URL.build(
                                scheme='vmess',
                                host=data['add'],
                                port=data['port'],
                            )),
                        'name':
                        data['ps'],
                        'fetcher':
                        self.name,
                        'net':
                        net,
                        'ws_path':
                        data['path'] or '/',
                        'ws_host':
                        data['host'] or data['add'],
                        'tls_host':
                        data.get('sni') or data['add'],
                        'userid':
                        data['id'],
                    }))
            except Exception as e:
                self.logger.warning('except while fetching %s: %s', url, e)

        return outboxes
