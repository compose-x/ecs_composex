#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Core ECS Template building
"""

from troposphere import GetAtt, Ref, Sub
from troposphere.iam import PolicyType
from troposphere.logs import LogGroup

from ecs_composex.common import add_update_mapping
from ecs_composex.common.cfn_params import ROOT_STACK_NAME, ROOT_STACK_NAME_T
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_service import Service
from ecs_composex.secrets.secrets_params import RES_KEY as SECRETS_KEY


def create_log_group(family):
    """
    Function to create a new Log Group for the services
    :return:
    """
    svc_log = family.template.add_resource(
        LogGroup(
            ecs_params.LOG_GROUP_T,
            RetentionInDays=Ref(ecs_params.LOG_GROUP_RETENTION),
            LogGroupName=Sub(
                f"${{{ROOT_STACK_NAME.title}}}/"
                f"svc/ecs/${{{ecs_params.CLUSTER_NAME_T}}}/{family.logical_name}",
            ),
        ),
    )
    policy = PolicyType(
        f"{family.logical_name}LogGroupAccess",
        PolicyName=Sub(f"CloudWatchAccessForFamily{family.logical_name}"),
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                    "Effect": "Allow",
                    "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                    "Resource": [GetAtt(svc_log, "Arn")],
                }
            ],
        },
        Roles=[family.exec_role.name],
    )
    if (
        family.template
        and f"{family.logical_name}LogGroupAccess" not in family.template.resources
    ):
        family.template.add_resource(policy)


def get_service_family_name(services_families, service_name):
    """
    Function to return the root family name, representing the service stack name.

    :param services_families:
    :param service_name:
    :return: service stack name
    :rtype: str
    """
    for family_name in services_families:
        if service_name in services_families[family_name]:
            return family_name
    if service_name in services_families.keys():
        return service_name
    return None


def initialize_family_services(settings, family):
    """
    Function to handle creation of services within the same family.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if settings.secrets_mappings:
        add_update_mapping(family.template, SECRETS_KEY, settings.secrets_mappings)
        add_update_mapping(
            family.exec_role.stack.stack_template,
            SECRETS_KEY,
            settings.secrets_mappings,
        )
    family.init_task_definition()
    family.set_secrets_access()
    family.refresh()
    family.assign_policies()
    family.merge_capacity_providers()
    family.validate_capacity_providers(settings.ecs_cluster)
    family.ecs_service = Service(family, settings)
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
