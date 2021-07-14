#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Docker compose integration related function, wrapping transformation to Container definition.
"""

import re

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import FARGATE_MODES
from ecs_composex.vpc.vpc_maths import clpow2, nxtpow2

NUMBERS_REG = r"[^0-9.]"
MINIMUM_SUPPORTED = 4


def import_time_values_to_seconds(time_string, as_tuple=False):
    """
    Function to parse strings with h/m/s

    :param str time_string:
    :param bool as_tuple: Whether or not return a tuple (hours, minutes, seconds)
    :return: The number of seconds or tuple of time breakdown as ints
    :rtype: int, tuple(int, int, int)
    """
    time_re = re.compile(r"(?P<hours>\d+h)?(?P<minutes>\d+m)?(?P<seconds>\d+s)?")
    time_groups = time_re.match(time_string).groups()
    if not any(t for t in time_groups):
        raise ValueError(
            "The time provided",
            time_string,
            "Does not match the expected pattern",
            time_re.pattern,
        )
    hours = time_re.match(time_string).group("hours") or 0
    minutes = time_re.match(time_string).group("minutes") or 0
    seconds = time_re.match(time_string).group("seconds") or 0
    if hours:
        hours = int(re.sub(r"[^\d]", "", hours))
    if minutes:
        minutes = int(re.sub(r"[^\d]", "", minutes))
    if seconds:
        seconds = int(re.sub(r"[^\d]", "", seconds))
    if as_tuple:
        return (hours, minutes, seconds)
    seconds += (60 * minutes) + (60 * 60 * hours)
    return seconds


def handle_bytes_units(value, factor):
    """
    Function to handle KB use-case
    """
    amount = float(re.sub(NUMBERS_REG, "", value))
    if factor == pow(2, 10):
        unit = "KBytes"
    elif factor == pow(pow(2, 10), 2):
        unit = "Bytes"
    else:
        raise ValueError(
            "Factor is not valid.",
            factor,
            "Must be one of",
            [pow(2, 10), pow(pow(2, 10), 2)],
        )
    if amount < (MINIMUM_SUPPORTED * factor):
        LOG.warning(
            f"You set unit to {unit} and value is lower than {MINIMUM_SUPPORTED}MB. "
            "Setting to minimum supported by Docker"
        )
        return MINIMUM_SUPPORTED * factor
    else:
        final_amount = int(amount / factor)
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
        final_amount = handle_bytes_units(value, pow(pow(2, 10), 2))
    elif kb_pat.findall(value):
        final_amount = handle_bytes_units(value, pow(2, 10))
    elif mb_pat.findall(value):
        final_amount = int(amount)
    elif gb_pat.findall(value):
        unit = "GBytes"
        final_amount = int(amount) * pow(2, 10)
    else:
        raise ValueError(f"Could not parse {value} to units")
    LOG.debug(f"Computed unit for {value}: {unit}. Results into {final_amount}MB")
    return int(final_amount)


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
        LOG.warning(
            f"Value {cpu} is not valid for Fargate. Valid modes: {fargate_cpus}"
        )
        if fargate_cpu < fargate_cpus[0]:
            fargate_cpu = fargate_cpus[0]
        elif fargate_cpu > fargate_cpus[-1]:
            fargate_cpu = fargate_cpus[-1]
    fargate_ram = find_closest_ram_config(ram, FARGATE_MODES[fargate_cpu])
    if as_param_string:
        return f"{fargate_cpu}!{fargate_ram}"
    return fargate_cpu, fargate_ram
