# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Most commonly used functions shared across all modules.
"""

import re
from datetime import datetime as dt
from math import ceil, log
from uuid import uuid4

DATE = dt.utcnow().isoformat()
FILE_PREFIX = f'{dt.utcnow().strftime("%Y/%m/%d/%H%M")}/{str(uuid4().hex)[:6]}'
NONALPHANUM = re.compile(r"([^a-zA-Z\d]+)")


def clpow2(x):
    """
    Function to return the closest power of two from given x

    :param x: Number to look the closest power of two for

    :returns: int() closest power of two
    """
    return pow(2, int(log(x, 2) + 0.5))


def nxtpow2(x):
    """Function to find the next power of two from given x number

    :param x: number to look for the next power of two

    :returns: next power of two number
    """
    return int(pow(2, ceil(log(x, 2))))
