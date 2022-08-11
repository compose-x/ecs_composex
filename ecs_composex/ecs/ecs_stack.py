# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings

from troposphere import FindInMap, Ref

from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import (
    add_parameters,
    add_resource,
    add_update_mapping,
)
from ecs_composex.compose.compose_secrets.ecs_family_helpers import (
    set_repository_credentials,
)
from ecs_composex.compose.compose_services.env_files_helpers import (
    upload_services_env_files,
)
from ecs_composex.compose.compose_volumes.ecs_family_helpers import set_volumes
from ecs_composex.ecs import ecs_params, metadata
from ecs_composex.ecs.ecs_family import ServiceStack
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_service import EcsService
from ecs_composex.secrets.secrets_params import RES_KEY as SECRETS_KEY


def initialize_family_services(
    settings: ComposeXSettings, family: ComposeFamily
) -> None:
    """
    Function to handle creation of services within the same family.

    :param ecs_composex.ecs.ecs_family.ComposeFamily family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if settings.secrets_mappings:
        add_update_mapping(family.template, SECRETS_KEY, settings.secrets_mappings)
        add_update_mapping(
            family.iam_manager.exec_role.stack.stack_template,
            SECRETS_KEY,
            settings.secrets_mappings,
        )
    family.init_task_definition()
    family.set_secrets_access()
    family.ecs_service = EcsService(family)
    family.stack.Parameters.update(
        {
            ecs_params.SERVICE_NAME_T: family.logical_name,
            CLUSTER_NAME_T: Ref(CLUSTER_NAME),
            ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
        }
    )
    upload_services_env_files(family, settings)
    set_repository_credentials(family, settings)
    set_volumes(family)
    family.handle_alarms()


def handle_families_dependencies(
    settings: ComposeXSettings, families_post: list
) -> None:
    """
    Function to handle family to family services based on docker compose depends_on

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list families_post:
    """
    for family in families_post:
        for family_name in settings.families[family].services_depends_on:
            if family_name not in families_post:
                continue
            if (
                family_name not in settings.families[family].stack.DependsOn
                and family_name != settings.families[family].name
            ):
                LOG.info(f"Adding dependency between {family_name} and {family}")
                settings.families[family].stack.DependsOn.append(
                    settings.families[family_name].stack.title
                )


def add_compose_families(settings: ComposeXSettings) -> None:
    """
    Using existing ComposeFamily in settings, creates the ServiceStack
    and template

    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for family_name, family in settings.families.items():
        family.init_family()
        initialize_family_services(settings, family)
        add_parameters(
            family.template,
            [
                family.iam_manager.task_role.arn_param,
                family.iam_manager.task_role.name_param,
                family.iam_manager.exec_role.arn_param,
                family.iam_manager.exec_role.name_param,
            ],
        )
        family.stack.Parameters.update(
            {
                ecs_params.CLUSTER_NAME.title: settings.ecs_cluster.cluster_identifier,
                ecs_params.FARGATE_VERSION.title: FindInMap(
                    "ComposeXDefaults", "ECS", "PlatformVersion"
                ),
                family.iam_manager.task_role.arn_param.title: family.iam_manager.task_role.output_arn,
                family.iam_manager.task_role.name_param.title: family.iam_manager.task_role.output_name,
                family.iam_manager.exec_role.arn_param.title: family.iam_manager.exec_role.output_arn,
                family.iam_manager.exec_role.name_param.title: family.iam_manager.exec_role.output_name,
                ecs_params.SERVICE_HOSTNAME.title: family.family_hostname,
            }
        )
        family.template.metadata.update(metadata)
        add_resource(settings.root_stack.stack_template, family.stack)
        family.validate_compute_configuration_for_task(settings)

    families_stacks = [
        family
        for family in settings.root_stack.stack_template.resources
        if (
            family in settings.families
            and isinstance(settings.families[family].stack, ServiceStack)
        )
    ]
    handle_families_dependencies(settings, families_stacks)
