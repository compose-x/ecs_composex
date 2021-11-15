#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

from pytest import raises

from ecs_composex.ingress_settings import set_port_from_str


def test_valid_ports():

    ports_check = {
        "8080": {0: 8080, 1: 8080, 2: "tcp"},
        "8081:80": {0: 8081, 1: 80, 2: "tcp"},
        "22/udp": {0: 22, 1: 22, 2: "udp"},
        "4242:21/udp": {0: 4242, 1: 21, 2: "udp"},
    }
    for port_str, expectation in ports_check.items():
        result = set_port_from_str(port_str)
        for check_id in [0, 1, 2]:
            assert str(expectation[check_id]) == result[check_id]


def test_invalid_ports():

    invalid_ports = ["8080/icmp", "abcd", "1234567/udp"]
    for port_str in invalid_ports:
        with raises(ValueError):
            set_port_from_str(port_str)
