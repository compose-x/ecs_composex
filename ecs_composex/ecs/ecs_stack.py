# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.ecs_ingress.ecs_ingress_stack import XStack as EcsIngressStack

from troposphere import FindInMap, GetAtt, Ref

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
            ecs_params.SERVICE_NAME.title: family.name,
            CLUSTER_NAME_T: Ref(CLUSTER_NAME),
            ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
        }
    )
    upload_services_env_files(family, settings)
    set_repository_credentials(family, settings)
    set_volumes(family)
    family.handle_alarms()


def handle_families_dependencies(
    settings: ComposeXSettings, families_post: list[tuple[str, str]]
) -> None:
    """
    Function to handle family to family services based on docker compose depends_on.
    Given the stack name and the family (services) name can be different due to special chars,
    we need to evaluate each of the families for both names to make sure to find it.
    """
    for family_def in families_post:
        _family_title, _family_name = family_def
        for family_name in settings.families[_family_title].services_depends_on.keys():
            for __family_title, __family_def in settings.families.items():
                if __family_def.name == family_name:
                    family_title = __family_title
                    break
            else:
                continue
            if (
                family_title not in settings.families[_family_title].stack.DependsOn
                and family_title != settings.families[_family_title].name
            ):
                LOG.info(
                    f"Adding dependency between {family_name}|{family_title} and {_family_name}|{_family_title}"
                )
                settings.families[_family_title].stack.DependsOn.append(
                    settings.families[family_title].stack.title
                )


def add_compose_families(
    settings: ComposeXSettings, families_sg_stack: EcsIngressStack
) -> None:
    """
    Using existing ComposeFamily in settings, creates the ServiceStack
    and template
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
                families_sg_stack.services_mappings[family.name].parameter,
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
                families_sg_stack.services_mappings[
                    family.name
                ].parameter.title: GetAtt(
                    families_sg_stack.services_mappings[family.name].stack.title,
                    f"Outputs.{families_sg_stack.services_mappings[family.name].parameter.title}",
                ),
            }
        )
        family.template.metadata.update(metadata)
        add_resource(settings.root_stack.stack_template, family.stack)
        family.validate_compute_configuration_for_task(settings)

    families_stacks = [
        (family, settings.families[family].name)
        for family in settings.root_stack.stack_template.resources
        if (
            family in settings.families
            and isinstance(settings.families[family].stack, ServiceStack)
        )
    ]
    handle_families_dependencies(settings, families_stacks)
