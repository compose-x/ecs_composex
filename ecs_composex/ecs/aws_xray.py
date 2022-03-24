#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Simple class to manage AWS XRay sidecar
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from ecs_composex.common import LOG, add_parameters
from ecs_composex.compose.compose_services import ComposeService
from ecs_composex.ecs.ecs_params import AWS_XRAY_IMAGE, XRAY_IMAGE


class XRaySideCar(ComposeService):
    """ """

    init_name = "xray-daemon"
    init_definition = {
        "image": AWS_XRAY_IMAGE,
        "ports": [{"target": 2000, "protocol": "tcp"}],
        "deploy": {
            "resources": {"limits": {"cpus": float(32 / 1024), "memory": "256M"}},
        },
        "x-iam": {
            "ManagedPolicyArns": ["arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"]
        },
    }

    def __init__(self):
        super().__init__(self.init_name, self.init_definition)
        self.is_aws_sidecar = True
        self.is_essential = False

    def add_to_family(self, family: ComposeFamily) -> None:
        """
        Adds the container as a sidecar to the family in order to fulfil a specific purpose
        for an AWS Feature, here, add xray-daemon for dynamic tracing.

        :param ecs_composex.ecs.ecs_family.ComposeFamily family:
        """
        self.my_family = family
        family.add_managed_sidecar(self)
        self.set_parameters()
        self.set_as_dependency_to_family_services()

    def set_parameters(self) -> None:
        """
        Auto adds the XRAY image as parameter to the stack
        """
        if self.my_family.template and self.my_family.stack:
            add_parameters(self.my_family.template, [XRAY_IMAGE])

    def set_as_dependency_to_family_services(self) -> None:
        for service in self.my_family.ordered_services:
            if service.is_aws_sidecar:
                continue
            if service.depends_on and self.name not in service.depends_on:
                service.depends_on.append(self.name)
                LOG.info(f"{self.name} - Added as xray-daemon dependency")


def set_xray(family: ComposeFamily) -> None:
    """
    Automatically adds the xray-daemon sidecar to the task definition.

    Evaluates if any of the services x_ray is True to add.
    If any(True) then checks whether the xray-daemon container is already in the services.
    Should only be invoked once
    """
    want_xray = any([service.x_ray for service in family.services])
    have_xray_container = XRaySideCar.init_name in [
        service.name for service in family.services
    ]
    have_xray = any([isinstance(svc, XRaySideCar) for svc in family.services])
    if not have_xray and want_xray:
        xray_service = XRaySideCar()
        xray_service.add_to_family(family)
        xray_service.set_as_dependency_to_family_services()
    elif have_xray_container and want_xray:
        LOG.warning(
            f"{family.name}"
            "You defined a container named xray-daemon on top of using x-xray in one of the services. "
            "Not auto-adding xray-daemon"
        )
    elif have_xray:
        for service in family.services:
            if service.name == XRaySideCar.init_name and isinstance(
                service, XRaySideCar
            ):
                xray_service = service
                break
        else:
            raise AttributeError(
                "Failed to identify the already defined x-ray service",
                [svc.name for svc in family.services],
            )
        xray_service.set_as_dependency_to_family_services()
