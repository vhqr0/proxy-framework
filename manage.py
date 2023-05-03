#!/usr/bin/env python3
# flake8: noqa

import proxy.contrib.proxy as _
import proxy.contrib.v2rayn as _

from proxy.manager import Manager

if __name__ == '__main__':
    Manager.main()
