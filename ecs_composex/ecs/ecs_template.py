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


def format_label(labels, svc_labels):
    """
    Function to format the label key value if labels are strings in a list

    :param dict labels: labels dict to update with new labels
    :param list svc_labels: the label string
    """
    for label in svc_labels:
        if isinstance(label, str) and label.find("=") > 0:
            splits = label.split("=")
            labels[label] = {splits[0]: splits[1]}
        elif isinstance(label, dict):
            labels.update(label)


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
    labels = None
    deploy_key = "deploy"
    labels_key = "labels"
    svc_labels = {}
    if keyisset(deploy_key, service_definition):
        if keyisset(labels_key, service_definition[deploy_key]):
            labels = service_definition[deploy_key][labels_key]
            LOG.info(f"labels: {labels}")
    if labels:
        if isinstance(labels, dict):
            return labels
        elif isinstance(labels, list):
            for item in labels:
                if not isinstance(item, str):
                    raise TypeError(
                        f"When using a list for deploy labels, all labels must be of type string"
                    )
                elif item.finds("=") > 0:
                    svc_labels.update({item.split("=")[0]: item.split("=")[1]})
        return svc_labels
    return {}


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
        svc_labels = get_deploy_labels(service)
        LOG.info(f"service {service_name} - labels {svc_labels}")
        if isinstance(svc_labels, list):
            format_label(labels, svc_labels)
        elif isinstance(svc_labels, dict):
            labels.update(svc_labels)
        update_families(families, labels, service_name)
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
        LOG.debug(f"Service {service_name} added.")
        services[service_name] = service
    return services


def handle_families_services(families, cluster_sg, content, **kwargs):
    """
    Function to handle creation of services within the same family.
    :return:
    """
    services = {}
    for family_name in families:
        family_resource_name = NONALPHANUM.sub("", family_name)
        containers = []
        template = initialize_service_template(family_resource_name)
        family = families[family_name]
        family_config = None
        family_parameters = {}
        for service_name in family:
            service = content[ecs_params.RES_KEY][service_name]
            service_config = ServiceConfig(
                content, service_name, service, family_name=family_resource_name
            )
            service_container = Container(
                template,
                service_config.resource_name,
                content[ecs_params.RES_KEY][service_name],
                config=service_config,
            )
            family_parameters.update(service_container.template_parameters)
            containers.append(service_container)
            if family_config is None:
                family_config = service_config
            else:
                family_config += service_config
        task = Task(template, [c.definition for c in containers], family_config)
        family_parameters.update(task.stack_parameters)
        service = Service(
            template, family_resource_name, task.definition, family_config, **kwargs
        )
        service.parameters.update(
            {
                CLUSTER_NAME_T: Ref(CLUSTER_NAME),
                ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
                ecs_params.CLUSTER_SG_ID_T: Ref(cluster_sg),
                vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID_T),
            }
        )
        service.parameters.update(family_parameters)
        LOG.debug(f"Service {family_resource_name} added.")
        services[family_resource_name] = service
    return services


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
    services.update(
        handle_families_services(families, cluster_sg, compose_content, **kwargs)
    )
    return services
