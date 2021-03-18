#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille<john@compose-x.io>

from pytest import raises

from ecs_composex.ingress_settings import generate_security_group_props


def test_cidr_validation():
    a = generate_security_group_props({"IPv4": "1.1.1.1/32"})
    with raises(ValueError):
        a = generate_security_group_props({"IPv4": "1.1.1.256/32"})
        a = generate_security_group_props({"IPv4": "1.1.1.1/33"})
