#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.ecs_ingress.ecs_ingress_stack import XStack as EcsIngressStack

from ecs_composex.common.stacks import ComposeXStack


def add_iam_dependency(iam_stack: ComposeXStack, family: ComposeFamily):
    """
    Adds the IAM Stack as dependency to the family one if not set already

    :param ecs_composex.common.stacks.ComposeXStack iam_stack:
    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    """
    if iam_stack and iam_stack.title not in family.stack.DependsOn:
        family.stack.DependsOn.append(iam_stack.title)


def handle_families_cross_dependencies(
    settings: ComposeXSettings,
    families_sg_stack: EcsIngressStack,
):
    from ecs_composex.ecs.ecs_family import ServiceStack
    from ecs_composex.ecs.service_networking.ingress_helpers import (
        set_compose_services_ingress,
    )

    eval_families: list[ComposeFamily] = []
    for _family in settings.families.values():
        if isinstance(_family.stack, ServiceStack):
            eval_families.append(_family)
    for _dst_family in eval_families:
        set_compose_services_ingress(
            _dst_family,
            families_sg_stack,
            settings,
        )


def set_families_ecs_service(settings: ComposeXSettings):
    """
    Sets the ECS Service in the family.ecs_service from ServiceConfig and family settings
    """
    for family in settings.families.values():
        family.ecs_service.generate_service_definition(family)
        family.service_scaling.create_scalable_target()
        family.service_scaling.add_target_scaling()
        family.service_scaling.add_scheduled_actions()
