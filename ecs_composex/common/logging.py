#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

import logging as logthings
import sys


class MyFormatter(logthings.Formatter):
    default_format = "%(asctime)s [%(levelname)8s] %(message)s"
    debug_format = "%(asctime)s [%(levelname)8s] (%(filename)s.%(lineno)d , %(funcName)s,) %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    def format(self, record) -> str:
        if record.levelno == logthings.DEBUG:
            formatter = logthings.Formatter(self.debug_format, self.date_format)
        else:
            formatter = logthings.Formatter(self.default_format, self.date_format)
        return formatter.format(record)


class InfoFilter(logthings.Filter):
    """Inspired from https://stackoverflow.com/a/16066513"""

    def filter(self, rec):
        return rec.levelno in (logthings.DEBUG, logthings.INFO)


class ErrorFilter(logthings.Filter):
    """Inspired from https://stackoverflow.com/a/16066513"""

    def filter(self, rec):
        return rec.levelno not in (logthings.DEBUG, logthings.INFO)


def setup_logging():
    """ """
    root_logger = logthings.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)

    app_logger = logthings.getLogger("ecs-compose-x")

    for h in app_logger.handlers:
        root_logger.removeHandler(h)

    stdout_handler = logthings.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(MyFormatter())
    stdout_handler.setLevel(logthings.INFO)
    stdout_handler.addFilter(InfoFilter())

    stderr_handler = logthings.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(MyFormatter())
    stderr_handler.setLevel(logthings.WARNING)
    stderr_handler.addFilter(ErrorFilter())

    app_logger.addHandler(stdout_handler)
    app_logger.addHandler(stderr_handler)
    app_logger.setLevel(logthings.INFO)
    return app_logger


LOG = setup_logging()
