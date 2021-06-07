#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
3 Layers subnets calculator for 3-tier VPC
"""

import ipaddress
from math import ceil, log

pow2_2_prefix = {
    "16": 28,
    "32": 27,
    "64": 26,
    "128": 25,
    "256": 24,
    "512": 23,
    "1024": 22,
    "2048": 21,
    "4096": 20,
    "8192": 19,
    "16384": 18,
    "32768": 17,
    "65536": 16,
    "131072": 15,
    "262144": 14,
    "524288": 13,
    "1048576": 12,
    "2097152": 11,
    "4194304": 10,
    "8388608": 9,
    "16777216": 8,
}


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


def cut_per_az(az_cidr, layers_cidr):
    """Subdivide the range per AZ in the region

    :param az_cidr: CIDR to split
    :param layers_cidr: dict() getting updated with layers

    :returns: NIL
    """
    maj_splits = list(az_cidr.subnets(prefixlen_diff=1))
    layers_cidr["app"].append(maj_splits[0])
    min_splits = list(maj_splits[1].subnets(prefixlen_diff=1))
    layers_cidr["pub"].append(min_splits[0])
    layers_cidr["stor"].append(min_splits[1])


def get_subnets(cidr, azs):
    """
    Get the lists of Subnets CIDRs
    """
    cidr = f"{cidr}"
    vpc_net = ipaddress.IPv4Network(cidr)
    number_ips = int(vpc_net.num_addresses - 2)

    if (azs != 2) and (azs % 2):
        azs += 1

    layers_cidr = {"app": [], "pub": [], "stor": []}

    ips_per_az = number_ips / azs
    pow2 = clpow2(ips_per_az)
    azs_prefix = pow2_2_prefix["%d" % (pow2)]
    subnets_per_az = list(vpc_net.subnets(new_prefix=azs_prefix))

    for az in subnets_per_az:
        cut_per_az(az, layers_cidr)
    return layers_cidr


def get_subnet_layers(cidr, azs):
    """
    Get Subnets layers based on number of AZs
    """
    layers = get_subnets(cidr, azs)
    cidrs = {}

    for layer in layers:
        cidrs[layer] = []
        sub_list = []
        for subnet in layers[layer]:
            sub_list.append("%s" % (subnet))
        cidrs[layer] = sub_list

    return cidrs
