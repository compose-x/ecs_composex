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

""" Core ECS Template building """

from troposphere import Ref, Sub, Tags, Join
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import keyisset
from ecs_composex.common import LOG, NONALPHANUM
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import (
    CLUSTER_NAME,
    CLUSTER_NAME_T,
    ECS_TASK_FAMILY_LABEL,
)
from ecs_composex.ecs.ecs_service import (
    Service,
    ServiceConfig,
    Container,
    Task,
    initialize_service_template,
)
from ecs_composex.vpc import vpc_params


class ServiceStack(ComposeXStack):
    """
    Class to handle individual ecs_service stack
    """

    def __init__(
        self, title, template, service, template_file=None, extension=None, **kwargs
    ):
        self.service = service
        super().__init__(title, template, template_file, extension, **kwargs)
        if not keyisset("Parameters", kwargs):
            self.Parameters = {
                ROOT_STACK_NAME_T: Ref("AWS::StackName"),
                vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
                vpc_params.PUBLIC_SUBNETS_T: Join(",", Ref(vpc_params.PUBLIC_SUBNETS)),
                vpc_params.APP_SUBNETS_T: Join(",", Ref(vpc_params.APP_SUBNETS)),
            }


def validate_input(services):
    """
    Validates services docker format
    """
    props_must_have = ["image"]
    for service_name in services:
        service = services[service_name]
        for prop in props_must_have:
            if not keyisset(prop, service):
                raise KeyError("Service {service_name} is missing property {prop}")
    return True


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


def define_families(services):
    """
    Function to group services together into a task family
    :param dict services:
    :return:
    """
    families = {}
    for service_name in services:
        labels = {}
        service = services[service_name]
        svc_labels = service["labels"] if keyisset("labels", service) else {}
        LOG.info(f"{service_name}")
        LOG.info(svc_labels)
        if isinstance(svc_labels, list):
            for label in svc_labels:
                if isinstance(label, str) and label.find("=") > 0:
                    splits = label.split("=")
                    labels[label] = {splits[0]: splits[1]}
                elif isinstance(label, dict):
                    labels.update(label)
        elif isinstance(svc_labels, dict):
            labels.update(svc_labels)
        for label in labels:
            if label == ECS_TASK_FAMILY_LABEL:
                family_name = labels[label]
                if not keyisset(family_name, families):
                    families[family_name] = [service_name]
                elif keyisset(family_name, families):
                    families[family_name].append(service_name)
    return families


def handle_single_services(single_services, cluster_sg, compose_content, **kwargs):
    """
    Function to handle the single services
    :return:
    """
    services = {}
    for service_name in single_services:
        service_definition = single_services[service_name]
        service_config = ServiceConfig(
            compose_content, service_name, service_definition
        )
        service_resource_name = NONALPHANUM.sub("", service_name)
        template = initialize_service_template(service_config.resource_name)
        container = Container(
            template, service_resource_name, service_definition, config=service_config
        )
        task = Task(template, [container.definition], service_config)
        service = Service(
            template, service_name, task.definition, service_config, **kwargs
        )
        service.parameters.update(
            {
                CLUSTER_NAME_T: Ref(CLUSTER_NAME),
                ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
                ecs_params.CLUSTER_SG_ID_T: Ref(cluster_sg),
                vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID_T),
            }
        )
        print(template.to_yaml())
        service.dependencies.append(ecs_params.LOG_GROUP_T)
        LOG.debug(f"Service {service_name} added.")
        services[service_name] = service
    return services


def handle_families_services(families, content, **kwargs):
    """
    Function to handle creation of services within the same family.
    :return:
    """
    configs = []
    for family_name in families:
        family = families[family_name]
        for service_name in family:
            service = content[ecs_params.RES_KEY][service_name]
            configs.append(ServiceConfig(content, service_name, service))


def generate_services(compose_content, cluster_sg, **kwargs):
    """
    Function putting together the ECS Service template

    :param compose_content: Docker/ComposeX file content
    :type compose_content: dict
    :param cluster_sg: cluster default security group
    :type cluster_sg: troposphere.ec2.SecurityGroup
    :param kwargs: optional arguments
    :type kwargs: dicts or set
    """
    services = {}
    in_family = []
    families = define_families(compose_content[ecs_params.RES_KEY])
    for family_name in families:
        family = families[family_name]
        for service in family:
            if service not in in_family:
                in_family.append(service)
    single_services = {}
    for service_name in compose_content[ecs_params.RES_KEY]:
        if service_name not in in_family:
            single_services[service_name] = compose_content[ecs_params.RES_KEY][
                service_name
            ]
    services.update(
        handle_single_services(single_services, cluster_sg, compose_content, **kwargs)
    )
    LOG.info(f"Singleservices, {single_services}")
    return services
