#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Docker compose integration related function, wrapping transformation to Container definition.
"""

import re

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import FARGATE_MODES
from ecs_composex.vpc.vpc_maths import clpow2, nxtpow2

NUMBERS_REG = r"[^0-9.]"
MINIMUM_SUPPORTED = 4


def handle_bytes(value):
    """
    Function to handle the KB use-case

    :param value: the string value
    :rtype: int or Ref(AWS_NO_VALUE)
    """
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "Bytes"
    if amount < (MINIMUM_SUPPORTED * 1024 * 1024):
        LOG.warn(
            f"You set unit to {unit} and value is lower than 4MB. Setting to minimum supported by Docker"
        )
        return MINIMUM_SUPPORTED
    else:
        final_amount = (amount / 1024) / 1024
    return final_amount


def handle_kbytes(value):
    """
    Function to handle KB use-case
    """
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "KBytes"
    if amount < (MINIMUM_SUPPORTED * 1024):
        LOG.warn(
            f"You set unit to {unit} and value is lower than 512MB. Setting to minimum supported by Docker"
        )
        return MINIMUM_SUPPORTED
    else:
        final_amount = int(amount / 1024)
    return final_amount


def set_memory_to_mb(value):
    """
    Returns the value of MB. If no unit set, assuming MB
    :param value: the string value
    :rtype: int or Ref(AWS_NO_VALUE)
    """
    b_pat = re.compile(r"(^[0-9.]+(b|B)$)")
    kb_pat = re.compile(r"(^[0-9.]+(k|kb|kB|Kb|K|KB)$)")
    mb_pat = re.compile(r"(^[0-9.]+(m|mb|mB|Mb|M|MB)$)")
    gb_pat = re.compile(r"(^[0-9.]+(g|gb|gB|Gb|G|GB)$)")
    amount = float(re.sub(NUMBERS_REG, "", value))
    unit = "MBytes"
    if b_pat.findall(value):
        final_amount = handle_bytes(value)
    elif kb_pat.findall(value):
        final_amount = handle_kbytes(value)
    elif mb_pat.findall(value):
        final_amount = int(amount)
    elif gb_pat.findall(value):
        unit = "GBytes"
        final_amount = int(amount) * 1024
    else:
        raise ValueError(f"Could not parse {value} to units")
    LOG.debug(f"Computed unit for {value}: {unit}. Results into {final_amount}MB")
    return final_amount


def find_closest_ram_config(ram, ram_range):
    """
    Function to find the closest RAM configuration

    :param int ram: amount of RAM we are trying to match up
    :param list ram_range: List of possible values for Fargate
    :return: the closest amount of RAM.
    :rtype: int
    """
    LOG.debug(f"{ram} - {ram_range[0]} - {ram_range[-1]}")
    if ram >= ram_range[-1]:
        return ram_range[-1]
    elif ram <= ram_range[0]:
        return ram_range[0]
    else:
        for ram_value in ram_range:
            if ram <= ram_value:
                LOG.debug(f"BEST RAM FOUND: {ram_value}")
                return ram_value


def find_closest_fargate_configuration(cpu, ram, as_param_string=False):
    """
    Function to get the closest Fargate CPU / RAM Configuration out of a CPU and RAM combination.

    :param int cpu: CPU count for the Task Definition
    :param int ram: RAM in MB for the Task Definition
    :param bool as_param_string: Returns the value as a CFN Fargate Configuration.
    :return:
    """
    fargate_cpus = list(FARGATE_MODES.keys())
    fargate_cpus.sort()
    fargate_cpu = clpow2(cpu)
    if fargate_cpu < cpu:
        fargate_cpu = nxtpow2(cpu)
    if fargate_cpu not in fargate_cpus:
        LOG.warn(f"Value {cpu} is not valid for Fargate. Valid modes: {fargate_cpus}")
        if fargate_cpu < fargate_cpus[0]:
            fargate_cpu = fargate_cpus[0]
        elif fargate_cpu > fargate_cpus[-1]:
            fargate_cpu = fargate_cpus[-1]
    fargate_ram = find_closest_ram_config(ram, FARGATE_MODES[fargate_cpu])
    if as_param_string:
        return f"{fargate_cpu}!{fargate_ram}"
    return fargate_cpu, fargate_ram
