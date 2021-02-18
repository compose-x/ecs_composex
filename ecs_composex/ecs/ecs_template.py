# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Core ECS Template building
"""

from troposphere import AWS_ACCOUNT_ID, AWS_PARTITION, AWS_REGION, AWS_NO_VALUE
from troposphere import If
from troposphere import Ref, Sub, Tags, GetAtt
from troposphere.ec2 import SecurityGroup
from troposphere.iam import PolicyType
from troposphere.logs import LogGroup

from ecs_composex.common import build_template, LOG
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    ROOT_STACK_NAME,
)
from ecs_composex.dns import dns_params, dns_conditions
from ecs_composex.dns.dns_conditions import (
    CREATE_PUBLIC_NAMESPACE_CON_T,
    CREATE_PUBLIC_NAMESPACE_CON,
)
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    CLUSTER_NAME_T,
)
from ecs_composex.ecs.ecs_service import (
    Service,
)
from ecs_composex.ecs.ecs_service_config import ServiceConfig
from ecs_composex.secrets.secrets_params import RES_KEY as SECRETS_KEY
from ecs_composex.vpc import vpc_params


def initialize_service_template(service_name):
    """Function to initialize the base template for ECS Services with all
    parameters and conditions necessary for CFN to work properly

    :param service_name: Name of the ecs_service as defined in ComposeX File
    :type service_name: str

    :return: service_template
    :rtype: troposphere.Template
    """
    service_tpl = build_template(
        f"Template for {service_name}",
        [
            dns_params.PUBLIC_DNS_ZONE_NAME,
            dns_params.PRIVATE_DNS_ZONE_NAME,
            dns_params.PUBLIC_DNS_ZONE_ID,
            dns_params.PRIVATE_DNS_ZONE_ID,
            dns_params.PRIVATE_NAMESPACE_ID,
            ecs_params.CLUSTER_NAME,
            ecs_params.LAUNCH_TYPE,
            ecs_params.ECS_CONTROLLER,
            ecs_params.SERVICE_COUNT,
            ecs_params.CLUSTER_SG_ID,
            ecs_params.SERVICE_HOSTNAME,
            ecs_params.FARGATE_CPU_RAM_CONFIG,
            ecs_params.SERVICE_NAME,
            ecs_params.LOG_GROUP_RETENTION,
            ecs_params.ELB_GRACE_PERIOD,
            ecs_params.FARGATE_VERSION,
            ecs_params.LOG_GROUP_NAME,
            ecs_params.CREATE_LOG_GROUP,
            vpc_params.VPC_ID,
            vpc_params.APP_SUBNETS,
            vpc_params.PUBLIC_SUBNETS,
        ],
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_CON_T, ecs_conditions.SERVICE_COUNT_ZERO_CON
    )
    service_tpl.add_condition(
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON_T,
        ecs_conditions.SERVICE_COUNT_ZERO_AND_FARGATE_CON,
    )
    service_tpl.add_condition(
        ecs_conditions.USE_HOSTNAME_CON_T, ecs_conditions.USE_HOSTNAME_CON
    )
    service_tpl.add_condition(
        ecs_conditions.NOT_USE_HOSTNAME_CON_T, ecs_conditions.NOT_USE_HOSTNAME_CON
    )
    service_tpl.add_condition(
        ecs_conditions.NOT_USE_CLUSTER_SG_CON_T, ecs_conditions.NOT_USE_CLUSTER_SG_CON
    )
    service_tpl.add_condition(
        ecs_conditions.USE_CLUSTER_SG_CON_T, ecs_conditions.USE_CLUSTER_SG_CON
    )
    service_tpl.add_condition(
        ecs_conditions.USE_FARGATE_CON_T,
        ecs_conditions.USE_FARGATE_CON,
    )
    service_tpl.add_condition(
        ecs_conditions.USE_CLUSTER_CAPACITY_PROVIDERS_CON_T,
        ecs_conditions.USE_CLUSTER_CAPACITY_PROVIDERS_CON,
    )
    service_tpl.add_condition(
        CREATE_PUBLIC_NAMESPACE_CON_T, CREATE_PUBLIC_NAMESPACE_CON
    )
    service_tpl.add_condition(
        ecs_conditions.CREATE_LOG_GROUP_CON_T, ecs_conditions.CREATE_LOG_GROUP_CON
    )
    service_tpl.add_condition(
        ecs_conditions.GENERATED_LOG_GROUP_NAME_CON_T,
        ecs_conditions.GENERATED_LOG_GROUP_NAME_CON,
    )
    service_tpl.add_condition(
        dns_conditions.PRIVATE_ZONE_ID_CON_T, dns_conditions.PRIVATE_ZONE_ID_CON
    )
    service_tpl.add_condition(
        dns_conditions.PRIVATE_NAMESPACE_CON_T, dns_conditions.PRIVATE_NAMESPACE_CON
    )
    return service_tpl


def create_log_group(service_tpl, family):
    """
    Function to create a new Log Group for the services
    :return:
    """
    svc_log = service_tpl.add_resource(
        LogGroup(
            ecs_params.LOG_GROUP_T,
            Condition=ecs_conditions.CREATE_LOG_GROUP_CON_T,
            RetentionInDays=Ref(ecs_params.LOG_GROUP_RETENTION),
            LogGroupName=If(
                ecs_conditions.GENERATED_LOG_GROUP_NAME_CON_T,
                Sub(
                    f"${{{ROOT_STACK_NAME.title}}}/"
                    f"svc/ecs/${{{ecs_params.CLUSTER_NAME_T}}}/${{{ecs_params.SERVICE_NAME_T}}}",
                ),
                Ref(ecs_params.LOG_GROUP_NAME),
            ),
        )
    )
    service_tpl.add_resource(
        PolicyType(
            "CloudWatchLogsAcccess",
            Roles=[Ref(ecs_params.EXEC_ROLE_T)],
            PolicyName=Sub(f"CloudWatchAccessFor${{{ecs_params.SERVICE_NAME_T}}}"),
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                        "Effect": "Allow",
                        "Action": [
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                            If(
                                ecs_conditions.GENERATED_LOG_GROUP_NAME_CON_T,
                                "logs:CreateLogGroup",
                                Ref(AWS_NO_VALUE),
                            ),
                        ],
                        "Resource": If(
                            ecs_conditions.CREATE_LOG_GROUP_CON_T,
                            [GetAtt(svc_log, "Arn")],
                            If(
                                ecs_conditions.GENERATED_LOG_GROUP_NAME_CON_T,
                                [
                                    Sub(
                                        f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                        f"log-group:${{{ROOT_STACK_NAME.title}}}/svc/ecs/"
                                        f"${{{ecs_params.CLUSTER_NAME_T}}}/${{{ecs_params.SERVICE_NAME_T}}}:*"
                                    ),
                                    Sub(
                                        f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                        f"${{{ROOT_STACK_NAME.title}}}log-group:svc/ecs/"
                                        f"${{{ecs_params.CLUSTER_NAME_T}}}/${{{ecs_params.SERVICE_NAME_T}}}"
                                    ),
                                ],
                                [
                                    Sub(
                                        f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                        f"log-group:${{{ecs_params.LOG_GROUP_NAME.title}}}:*"
                                    ),
                                    Sub(
                                        f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                                        f"log-group:${{{ecs_params.LOG_GROUP_NAME.title}}}"
                                    ),
                                ],
                            ),
                        ),
                    },
                ],
            },
        )
    )
    family.task_logging_options = {
        "awslogs-group": If(
            ecs_conditions.CREATE_LOG_GROUP_CON_T,
            Ref(svc_log),
            If(
                ecs_conditions.GENERATED_LOG_GROUP_NAME_CON_T,
                Sub(
                    f"svc/ecs/${{{ecs_params.CLUSTER_NAME_T}}}/${{{ecs_params.SERVICE_NAME_T}}}",
                ),
                Ref(ecs_params.LOG_GROUP_NAME),
            ),
        ),
        "awslogs-region": Ref(AWS_REGION),
        "awslogs-create-group": True,
    }


def add_clusterwide_security_group(template):
    """
    Function to generate the ecs_service Load Balancers (if Any)
    """
    sg = SecurityGroup(
        "ClusterWideSecurityGroup",
        template=template,
        GroupDescription=Sub(f"SG for ${{{CLUSTER_NAME_T}}}"),
        GroupName=Sub(f"cluster-${{{CLUSTER_NAME_T}}}"),
        Tags=Tags(
            {
                "Name": Sub(f"clustersg-${{{CLUSTER_NAME_T}}}"),
                "ClusterName": Ref(CLUSTER_NAME),
            }
        ),
        VpcId=Ref(vpc_params.VPC_ID),
    )
    return sg


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


def generate_services(settings):
    """
    Function to handle creation of services within the same family.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    for family_name in settings.families:
        family = settings.families[family_name]
        family.template = initialize_service_template(family_name)
        create_log_group(family.template, family)
        if settings.secrets_mappings:
            family.template.add_mapping(SECRETS_KEY, settings.secrets_mappings)
        family.init_task_definition()
        family.set_secrets_access()
        family.refresh()
        family.assign_policies()
        family.service_config = ServiceConfig(family, settings)
        family.ecs_service = Service(family, settings)
        family.service_config.network.set_aws_sources(
            family.logical_name, GetAtt(family.ecs_service.sg, "GroupId")
        )
        family.service_config.network.set_ext_sources_ingress(
            family.logical_name, GetAtt(family.ecs_service.sg, "GroupId")
        )
        family.service_config.network.associate_aws_igress_rules(family.template)
        family.service_config.network.associate_ext_igress_rules(family.template)
        family.stack_parameters.update(
            {
                ecs_params.SERVICE_NAME_T: family.logical_name,
                CLUSTER_NAME_T: Ref(CLUSTER_NAME),
                ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
            }
        )
        family.upload_services_env_files(settings)
        family.set_repository_credentials(settings)
        family.set_codeguru_profiles_arns()
        family.set_volumes()
