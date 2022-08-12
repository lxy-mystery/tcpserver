#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from logging import DEBUG, ERROR, WARN, WARNING, INFO, CRITICAL, NOTSET
config = {
    "server": {
        "port": 9437
    },
    "log": {
        "level": WARN,
        "file": "/home/ubuntu/log/server.log",
        "format": '%(asctime)s - %(levelname)s -%(process)d - %(message)s'
    }
}
