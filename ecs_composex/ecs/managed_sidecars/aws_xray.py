#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Simple class to manage AWS XRay sidecar
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from copy import deepcopy

from ecs_composex.common import LOG
from ecs_composex.ecs.ecs_params import XRAY_IMAGE

from . import ManagedSidecar

XRAY_NAME = "xray-daemon"
XRAY_DEFINITION = {
    "image": XRAY_IMAGE.Default,
    "ports": [{"target": 2000, "protocol": "tcp"}],
    "deploy": {
        "resources": {"limits": {"cpus": float(32 / 1024), "memory": "256M"}},
    },
    "x-iam": {
        "ManagedPolicyArns": ["arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"]
    },
}

XRAY_SERVICE = ManagedSidecar("xray-daemon", XRAY_DEFINITION)


def set_xray(family: ComposeFamily) -> None:
    """
    Automatically adds the xray-daemon sidecar to the task definition.

    Evaluates if any of the services x_ray is True to add.
    If any(True) then checks whether the xray-daemon container is already in the services.
    Should only be invoked once

    The XRAY service is marked as a dependency to family services as some services with XRAY
    collection will fail if for some reason the daemon is not started yet.
    """
    want_xray = any([service.x_ray for service in family.services])
    have_xray_container = XRAY_NAME in [service.name for service in family.services]
    have_xray = any(
        [
            isinstance(svc, ManagedSidecar)
            for svc in family.services
            if svc.name == XRAY_NAME
        ]
    )
    if not have_xray and want_xray:
        xray_service = deepcopy(XRAY_SERVICE)
        xray_service.add_to_family(family, is_dependency=True)
    elif have_xray_container and want_xray:
        LOG.warning(
            f"{family.name}"
            "You defined a container named xray-daemon on top of using x-xray in one of the services. "
            "Not auto-adding xray-daemon"
        )
    elif have_xray:
        for service in family.services:
            if service.name == XRAY_NAME and isinstance(service, ManagedSidecar):
                xray_service = service
                break
        else:
            raise AttributeError(
                "Failed to identify the already defined x-ray service",
                [svc.name for svc in family.services],
            )
        xray_service.set_as_dependency_to_family_services(is_dependency=True)
