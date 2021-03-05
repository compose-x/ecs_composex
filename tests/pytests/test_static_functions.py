# Copyright 2020 - 2021, John Mille (john@compose-x.io) and the ECS Compose-X contributors
# SPDX-License-Identifier: GPL-2.0-only


from pytest import raises

from ecs_composex.ingress_settings import generate_security_group_props


def test_cidr_validation():
    a = generate_security_group_props({"IPv4": "1.1.1.1/32"})
    with raises(ValueError):
        a = generate_security_group_props({"IPv4": "1.1.1.256/32"})
        a = generate_security_group_props({"IPv4": "1.1.1.1/33"})
