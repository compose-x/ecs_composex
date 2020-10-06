# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
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

from troposphere import Ref, Sub, Tags, GetAtt
from troposphere.ec2 import SecurityGroup
from troposphere.iam import PolicyType
from troposphere.logs import LogGroup

from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common import build_template
from ecs_composex.common import keyisset
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    ROOT_STACK_NAME,
)
from ecs_composex.dns import dns_params
from ecs_composex.dns.dns_conditions import (
    CREATE_PUBLIC_NAMESPACE_CON_T,
    CREATE_PUBLIC_NAMESPACE_CON,
)
from ecs_composex.ecs import ecs_conditions, ecs_params
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    CLUSTER_NAME_T,
    ECS_TASK_FAMILY_LABEL,
)
from ecs_composex.ecs.ecs_service import (
    Service,
    Task,
)
from ecs_composex.ecs.ecs_service_config import ServiceConfig
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
            ecs_params.CLUSTER_NAME,
            ecs_params.LAUNCH_TYPE,
            ecs_params.ECS_CONTROLLER,
            ecs_params.SERVICE_COUNT,
            ecs_params.CLUSTER_SG_ID,
            vpc_params.VPC_ID,
            vpc_params.APP_SUBNETS,
            vpc_params.PUBLIC_SUBNETS,
            ecs_params.SERVICE_HOSTNAME,
            ecs_params.FARGATE_CPU_RAM_CONFIG,
            ecs_params.SERVICE_NAME,
            ecs_params.LOG_GROUP_RETENTION,
            ecs_params.ELB_GRACE_PERIOD,
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
    svc_log = service_tpl.add_resource(
        LogGroup(
            ecs_params.LOG_GROUP_T,
            RetentionInDays=Ref(ecs_params.LOG_GROUP_RETENTION),
            LogGroupName=Sub(
                f"svc/${{{ecs_params.CLUSTER_NAME_T}}}/${{{ecs_params.SERVICE_NAME_T}}}"
            ),
        )
    )
    service_tpl.add_resource(
        PolicyType(
            "CloudWatchAcccess",
            Roles=[Ref(ecs_params.EXEC_ROLE_T)],
            PolicyName=Sub(f"CloudWatchAccessFor${{{ecs_params.SERVICE_NAME_T}}}"),
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowCloudWatchLoggingToSpecificLogGroup",
                        "Effect": "Allow",
                        "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                        "Resource": [GetAtt(svc_log, "Arn")],
                    },
                ],
            },
        )
    )
    return service_tpl


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


def parse_string_labels(labels, svc_labels):
    """
    Function to format the label key value if labels are strings in a list

    :param dict labels: labels dict to update with new labels
    :param list svc_labels: the label string
    """
    for label in svc_labels:
        if label.find("=") > 0:
            splits = label.split("=")
            labels.update({splits[0]: splits[1]})


def update_families(families, labels, service_name):
    """
    Function to update families info from labels

    :param dict families: registry of applications families
    :param dict labels: the list of labels from a a service
    :param str service_name: name of the service for which we get these labels
    """
    for label in labels:
        if label == ECS_TASK_FAMILY_LABEL:
            family_name = labels[label]
            if not keyisset(family_name, families):
                families[family_name] = [service_name]
            elif keyisset(family_name, families):
                families[family_name].append(service_name)


def get_deploy_labels(service_definition):
    """
    Function to get the deploy labels of a service definition

    :param dict service_definition: The service definition as defined in compose file
    :return: labels if any
    :rtype: dict
    """
    labels = {}
    deploy_key = "deploy"
    labels_key = "labels"
    svc_labels = {}
    if keyisset(deploy_key, service_definition) and keyisset(
        labels_key, service_definition[deploy_key]
    ):
        svc_labels = service_definition[deploy_key][labels_key]
        LOG.debug(f"labels: {svc_labels}")
    if svc_labels:
        if isinstance(svc_labels, list):
            for item in svc_labels:
                if not isinstance(item, str):
                    raise TypeError(
                        "When using a list for deploy labels, all labels must be of type string"
                    )
                parse_string_labels(labels, svc_labels)
        elif isinstance(svc_labels, dict):
            return svc_labels
    return labels


def define_services_families(services):
    """
    Function to group services together into a task family

    :param dict services:
    :return:
    """
    families = {}
    for service_name in services:
        labels = {}
        service = services[service_name]
        svc_labels = get_deploy_labels(service.definition)
        LOG.debug(f"service {service_name} - labels {svc_labels}")
        labels.update(svc_labels)
        if not labels:
            labels = {ECS_TASK_FAMILY_LABEL: service_name}
        update_families(families, labels, service_name)
    return families


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


def handle_families_services(families, cluster_sg, settings):
    """
    Function to handle creation of services within the same family.
    :return:
    """
    services = {}
    for family_name in families:
        family_resource_name = NONALPHANUM.sub("", family_name)
        template = initialize_service_template(family_resource_name)
        family = families[family_name]
        family_service_configs = {}
        family_parameters = {}
        for service_name in family:
            service = settings.compose_content[ecs_params.RES_KEY][service_name]
            if keyisset("deploy", service.definition):
                service.definition["deploy"].update(
                    get_deploy_labels(service.definition)
                )
                LOG.debug(service.definition["deploy"])
            service_config = ServiceConfig(
                service,
                settings.compose_content,
                family_name=family_resource_name,
            )
            family_service_configs[service_name] = {
                "config": service_config,
                "priority": 0,
                "definition": service,
            }
        task = Task(template, family_service_configs, family_parameters, settings)
        family_parameters.update(task.stack_parameters)
        service = Service(
            template=template,
            family_name=family_resource_name,
            task_definition=task,
            config=task.family_config,
            settings=settings,
        )
        service.parameters.update(
            {
                CLUSTER_NAME_T: Ref(CLUSTER_NAME),
                ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
                ecs_params.CLUSTER_SG_ID_T: Ref(cluster_sg),
                dns_params.PRIVATE_DNS_ZONE_ID.title: Ref(
                    dns_params.PRIVATE_DNS_ZONE_ID
                ),
                dns_params.PRIVATE_DNS_ZONE_NAME.title: Ref(
                    dns_params.PRIVATE_DNS_ZONE_NAME
                ),
                dns_params.PUBLIC_DNS_ZONE_ID.title: Ref(dns_params.PUBLIC_DNS_ZONE_ID),
                dns_params.PUBLIC_DNS_ZONE_NAME.title: Ref(
                    dns_params.PUBLIC_DNS_ZONE_NAME
                ),
            }
        )
        service.parameters.update(family_parameters)
        LOG.debug(f"Service {family_resource_name} added.")
        services[family_resource_name] = service
    return services


def generate_services(settings, cluster_sg):
    """
    Function putting together the ECS Service template

    :param ComposeXSettings settings: The settings for execution
    :param troposphere.ec2.SecurityGroup cluster_sg: cluster default security group
    """
    families = define_services_families(settings.compose_content[ecs_params.RES_KEY])
    services = handle_families_services(families, cluster_sg, settings)
    return services
