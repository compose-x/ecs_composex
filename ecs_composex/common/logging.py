#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

import logging as logthings
import sys


def setup_logging():
    """ """
    default_format = logthings.Formatter(
        "%(asctime)s [%(levelname)8s] %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    debug_format = logthings.Formatter(
        "%(asctime)s [%(levelname)8s] %(filename)s.%(lineno)d , %(funcName)s, %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    root_logger = logthings.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)

    app_logger = logthings.getLogger("ecs-compose-x")

    for h in app_logger.handlers:
        root_logger.removeHandler(h)

    stdout_handler = logthings.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(default_format)
    stdout_handler.setLevel(logthings.INFO)

    stderr_handler = logthings.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(debug_format)
    stderr_handler.setLevel(logthings.ERROR)

    app_logger.addHandler(stdout_handler)
    app_logger.addHandler(stderr_handler)
    app_logger.setLevel(logthings.INFO)
    return app_logger


LOG = setup_logging()
