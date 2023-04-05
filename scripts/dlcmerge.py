#!/usr/bin/env python3
"""DLC(domain list community) merger.

Merge https://github.com/v2fly/domain-list-community to a rules file.
Only (domain, full) in (domain, full, keyword, regexp) are supported.
MultiTags is not supported. (So far it doesn't seem to be used)
"""

import argparse
import os.path
import re

parser = argparse.ArgumentParser()
parser.add_argument('-d',
                    '--data-path',
                    default=os.path.join('domain-list-community', 'data'))
args = parser.parse_args()

data_path = args.data_path

tag_dict = {
    'ads': 'block',
    'cn': 'direct',
    '!cn': 'forward',
}

line_re = re.compile(r'^((\w+):)?([^\s\t#]+)( @([^\s\t#]+))?')


def load_rules(rules_file: str, fallback_tag: str):
    for line in open(os.path.join(data_path, rules_file)):
        line_match = line_re.match(line.strip())
        if line_match is None:
            continue
        command = line_match[2] or 'domain'
        arg = line_match[3]
        tag = line_match[5] or fallback_tag
        rule = tag_dict[tag]
        if command in ('domain', 'full'):
            print(f'{rule}\t{arg}')
        elif command == 'include':
            load_rules(arg, fallback_tag)


load_rules('cn', 'cn')
load_rules('geolocation-!cn', '!cn')
