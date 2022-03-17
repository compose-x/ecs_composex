#   -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

from troposphere import FindInMap, Ref

from ecs_composex.common import LOG, add_parameters, add_update_mapping
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params, metadata
from ecs_composex.ecs.ecs_cluster.ecs_family_helpers import validate_capacity_providers
from ecs_composex.ecs.ecs_family.task_logging import create_log_group
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_service import EcsService
from ecs_composex.secrets.secrets_params import RES_KEY as SECRETS_KEY


class ServiceStack(ComposeXStack):
    """
    Class to identify specifically a service stack
    """


def initialize_family_services(settings, family):
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
    family.refresh()
    family.service_compute.set_update_capacity_providers()
    # merge_capacity_providers(family)
    validate_capacity_providers(family, settings.ecs_cluster)
    family.ecs_service = EcsService(family, settings)
    family.stack.Parameters.update(
        {
            ecs_params.SERVICE_NAME_T: family.logical_name,
            CLUSTER_NAME_T: Ref(CLUSTER_NAME),
            ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
        }
    )
    family.upload_services_env_files(settings)
    family.set_repository_credentials(settings)
    family.set_volumes()
    create_log_group(family)
    family.handle_logging()
    family.handle_alarms()
    family.validate_compute_configuration_for_task(settings)


def handle_families_dependencies(settings, families_post):
    """
    Function to handle family to family services based on docker compose depends_on

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param list families_post:
    """
    for family in families_post:
        for family_name in settings.families[family].services_depends_on:
            if family_name not in families_post:
                continue
            if family_name not in settings.families[family].stack.DependsOn:
                LOG.info(f"Adding dependency between {family_name} and {family}")
                settings.families[family].stack.DependsOn.append(
                    settings.families[family_name].stack.title
                )


def add_compose_families(root_stack, settings) -> None:
    """
    Using existing ComposeFamily in settings, creates the ServiceStack
    and template

    :param ecs_composex.common.stacks.ComposeXStack root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for family_name, family in settings.families.items():
        family.stack = ServiceStack(
            family.logical_name,
            stack_template=family.template,
            stack_parameters=family.stack_parameters,
        )
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
        if settings.ecs_cluster.platform_override:
            family.launch_type = settings.ecs_cluster.platform_override
            family.stack.Parameters.update(
                {ecs_params.LAUNCH_TYPE.title: settings.ecs_cluster.platform_override}
            )
        family.template.set_metadata(metadata)
        root_stack.stack_template.add_resource(family.stack)
        if settings.networks and family.service_networking.networks:
            family.update_family_subnets(settings)

    families_stacks = [
        family
        for family in root_stack.stack_template.resources
        if (
            family in settings.families
            and isinstance(settings.families[family].stack, ServiceStack)
        )
    ]
    handle_families_dependencies(settings, families_stacks)
