#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.compose.compose_services import ComposeService

import re

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import AWS_NO_VALUE, Ref
from troposphere.elasticloadbalancingv2 import Matcher, TargetGroupAttribute

from ecs_composex.common.logging import LOG

DEREGISTRATION_DELAY_TIMEOUT_SECONDS: str = "deregistration_delay.timeout_seconds"


def validate_props_and_service_definition(props: dict, service: ComposeService) -> None:
    """
    Function to validate that the defined settings are valid according to the service definition.
    :raises ValueError: if any of the settings are invalid
    """
    valid_tcp = ["HTTP", "HTTPS", "TLS", "TCP_UDP", "TCP"]
    valid_udp = ["UDP", "TCP_UDP"]
    if props["Port"] not in [p["target"] for p in service.ports]:
        raise ValueError(
            f"Defined TargetGroup port {props['Port']} is not defined for {service.name}."
            " Valid ports are",
            [
                _port["published"]
                for _port in service.ports
                if keyisset("published", _port)
            ],
        )
    chosen_port = [p for p in service.ports if p["target"] == props["Port"]]
    if (chosen_port[0]["protocol"] == "tcp" and props["Protocol"] not in valid_tcp) or (
        chosen_port[0]["protocol"] == "udp" and props["Protocol"] not in valid_udp
    ):
        raise ValueError(
            f"The protocol defined for TargetGroup {props['Protocol']} "
            f"does not match the service protocol {chosen_port[0]['protocol']}"
        )


def handle_ping_settings(props, ping_raw):
    ping_re = re.compile(r"^([\d]|10):([\d]|10):([\d]{1,3}):([\d]{1,3})$")
    groups = ping_re.match(ping_raw).groups()
    ping_mapping = (
        ("HealthyThresholdCount", (2, 10)),
        ("UnhealthyThresholdCount", (2, 10)),
        ("HealthCheckIntervalSeconds", (5, 300)),
        ("HealthCheckTimeoutSeconds", (2, 120)),
    )
    for count, value in enumerate(groups):
        if not min(ping_mapping[count][1]) <= int(value) <= max(ping_mapping[count][1]):
            LOG.error(
                f"Value for {ping_mapping[count][0]} is not valid. Must be in range of {ping_mapping[count][1]}"
            )
        props[ping_mapping[count][0]] = int(value)


def handle_path_settings(props: dict, path_raw: str) -> None:
    """
    Function to set the path and codes properties for health checks.
    Handles three formats:
    1. /:<codes> - Just codes with default path
    2. /path:<codes> - Custom path with codes
    3. <codes> - Just codes without path

    :param dict props: Properties dict to update
    :param str path_raw: Raw path/codes string to parse
    :return: None
    """
    # Regex pattern to match the three supported formats
    health_re = re.compile(
        r"(?P<shorty>^/:(?P<codes0>(?:[12345][0-9]{2},?){1,})$)|"  # Format 1
        r"(?P<long>(?P<path1>/[^:]+):(?P<codes1>(?:[12345][0-9]{2},?){1,})$)|"  # Format 2
        r"(?P<codesonly>(?:[12345][0-9]{2},?){1,})$"  # Format 3
    )

    match = health_re.search(path_raw)

    # Format 1: /:<codes>
    if match.group("shorty"):
        props["Matcher"] = Matcher(HttpCode=match.group("codes0"))

    # Format 2: /path:<codes>
    elif match.group("long"):
        props["HealthCheckPath"] = match.group("path1")
        props["Matcher"] = Matcher(HttpCode=match.group("codes1"))

    # Format 3: <codes>
    elif match.group("codesonly"):
        props["Matcher"] = Matcher(HttpCode=match.group("codesonly"))

    else:
        raise ValueError("Invalid health check path format")

    # Validate protocol compatibility
    if props["HealthCheckProtocol"] not in ["HTTP", "HTTPS"] and isinstance(
        props["Matcher"], Matcher
    ):
        raise ValueError(
            "Protocol and return codes are only valid for HTTP and HTTPS HealthCheck"
        )


def validate_target_group_attributes(target_attributes, validation, lb_type):
    """
    Function to ensure that each attribute set is compatible with elbv2.type == application

    :param list[TargetGroupAttribute] target_attributes:
    :param dict validation:
    :param str lb_type:
    :raises: ValueError
    """
    for attr in target_attributes:
        if attr.Key not in validation.keys():
            raise ValueError(
                f"Attribute {attr.Key} is not compatible with {lb_type}. Valid ones",
                validation.keys(),
            )
        evaluation = validation[attr.Key]
        if not evaluation(attr.Value):
            raise ValueError(f"{attr.Key} value {attr.Value} is not valid.")


def import_target_group_attributes(props: dict, target_def: dict, elbv2) -> None:
    """Function to do input validation to try avoid incompatible settings together"""
    attributes_key = "TargetGroupAttributes"
    if not keyisset(attributes_key, target_def):
        props[attributes_key] = [
            TargetGroupAttribute(Key=DEREGISTRATION_DELAY_TIMEOUT_SECONDS, Value="60")
        ]
    else:
        if isinstance(target_def[attributes_key], list):
            props[attributes_key] = [
                TargetGroupAttribute(Key=attr["Key"], Value=str(attr["Value"]))
                for attr in target_def[attributes_key]
            ]
        elif isinstance(target_def[attributes_key], dict):
            props[attributes_key] = [
                TargetGroupAttribute(Key=key, Value=str(value))
                for key, value in target_def[attributes_key].items()
            ]
    if not keyisset(attributes_key, props):
        props[attributes_key] = [
            TargetGroupAttribute(Key=DEREGISTRATION_DELAY_TIMEOUT_SECONDS, Value="60")
        ]
        return
    if DEREGISTRATION_DELAY_TIMEOUT_SECONDS not in [
        attr.Key for attr in props[attributes_key]
    ]:
        props[attributes_key].append(
            TargetGroupAttribute(Key=DEREGISTRATION_DELAY_TIMEOUT_SECONDS, Value="60")
        )
    nlb_valid = {
        "deregistration_delay.connection_termination.enabled": lambda x: x
        in ("true", "false"),
        "preserve_client_ip.enabled": lambda x: x in ("true", "false"),
        "proxy_protocol_v2.enabled": lambda x: x in ("true", "false"),
        "stickiness.type": lambda x: x == "source_ip",
        DEREGISTRATION_DELAY_TIMEOUT_SECONDS: lambda x: 0 <= int(x) <= 3600,
        "stickiness.enabled": lambda x: x in ("true", "false"),
    }
    alb_valid = {
        "stickiness.enabled": lambda x: x in ("true", "false"),
        "stickiness.type": lambda x: x in ("lb_cookie", "app_cookie"),
        "stickiness.app_cookie.cookie_name": lambda x: isinstance(x, str)
        and not re.match(r"^AWSALB.*$|^AWSALBAPP.*|^AWSALBTG.*$", x),
        "stickiness.app_cookie.duration_seconds": lambda x: 1 <= int(x) <= 604800,
        "stickiness.lb_cookie.duration_seconds": lambda x: 1 <= int(x) <= 604800,
        DEREGISTRATION_DELAY_TIMEOUT_SECONDS: lambda x: 0 <= int(x) <= 3600,
        "load_balancing.algorithm.type": lambda x: x
        in ("round_robin", "least_outstanding_requests"),
        "slow_start.duration_seconds": lambda x: 30 <= int(x) <= 900,
    }
    # pragma: ignore use-case for now "lambda.multi_value_headers.enabled": lambda x: x in ("true", "false"),
    if elbv2.lb_type == "application":
        validate_target_group_attributes(
            props[attributes_key], alb_valid, elbv2.lb_type
        )
    if elbv2.lb_type == "network":
        validate_target_group_attributes(
            props[attributes_key], nlb_valid, elbv2.lb_type
        )


def set_healthcheck_definition(
    props, target_definition, healtheck_keyword: str = "healthcheck"
):
    """

    :param dict props:
    :param dict target_definition:
    :return:
    """
    healthcheck_props = {
        "HealthCheckEnabled": Ref(AWS_NO_VALUE),
        "HealthCheckIntervalSeconds": Ref(AWS_NO_VALUE),
        "HealthCheckPath": Ref(AWS_NO_VALUE),
        "HealthCheckPort": Ref(AWS_NO_VALUE),
        "HealthCheckProtocol": Ref(AWS_NO_VALUE),
        "HealthCheckTimeoutSeconds": Ref(AWS_NO_VALUE),
        "HealthyThresholdCount": Ref(AWS_NO_VALUE),
    }
    healthcheck_reg = re.compile(
        r"(?:^(?P<port>[\d]{2,5}):(?P<protocol>HTTPS|HTTP|TCP_UDP|TCP|TLS|UDP|GENEVE)):?"
        r"(?P<ping>(?:[\d]{1}|10):(?:[\d]{1}|10):[\d]{1,3}:[\d]{1,3})?:?"
        r"(?P<health>(?:/[\S][^:]+.$)|(?:/[\S][^:]+)(?::)(?:(?:[\d]{1,4},?){1,}.$)|(?:(?:[\d]{1,4},?){1,}.$))?"
    )
    healthcheck_definition = set_else_none(healtheck_keyword, target_definition)
    if isinstance(healthcheck_definition, str):
        port, protocol, ping, health = healthcheck_reg.search(
            healthcheck_definition
        ).groups()
        if not port or not protocol:
            raise ValueError(
                f"You need to define at least the Protocol and port for {healtheck_keyword}"
            )
        healthcheck_props["HealthCheckPort"] = int(port)
        healthcheck_props["HealthCheckProtocol"] = protocol
        if ping:
            handle_ping_settings(healthcheck_props, ping_raw=ping)
        if health:
            try:
                handle_path_settings(healthcheck_props, health)
            except ValueError:
                LOG.error(target_definition["name"], target_definition["healthcheck"])
                raise
    elif isinstance(healthcheck_definition, dict):
        healthcheck_props.update(healthcheck_definition)
        if keyisset("Matcher", healthcheck_definition):
            healthcheck_props["Matcher"] = Matcher(**healthcheck_definition["Matcher"])
    else:
        raise TypeError(
            healthcheck_definition,
            type(healthcheck_definition),
            "must be one of",
            (str, dict),
        )
    props.update(healthcheck_props)
