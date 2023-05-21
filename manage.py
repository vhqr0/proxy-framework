#!/usr/bin/env python3
import proxy.contrib.basic  # noqa
import proxy.contrib.v2rayn  # noqa
from proxy.server.manager import Manager

if __name__ == '__main__':
    Manager.main()
