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
from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T, ROOT_STACK_NAME
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_service import Service
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


def generate_services(compose_content, cluster_sg, session=None, **kwargs):
    """Function putting together the ECS Service template

    :param compose_content: Docker/ComposeX file content
    :type compose_content: dict
    :param root_tpl: template
    :type root_tpl: troposphere.Template
    :param cluster_sg: cluster default security group
    :type cluster_sg: troposphere.ec2.SecurityGroup
    :param session: override default session
    :type session: boto3.session.Session
    :param kwargs: optional arguments
    :type kwargs: dicts or set
    """
    services = {}
    for service_name in compose_content[ecs_params.RES_KEY]:
        service_definition = compose_content[ecs_params.RES_KEY][service_name]
        service = Service(service_name, service_definition, compose_content, **kwargs)
        service.parameters.update(
            {
                CLUSTER_NAME_T: Ref(CLUSTER_NAME),
                ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
                ecs_params.CLUSTER_SG_ID_T: Ref(cluster_sg),
                vpc_params.VPC_MAP_ID_T: Ref(vpc_params.VPC_MAP_ID_T),
            }
        )
        if keyisset("hostname", service.definition):
            service.parameters.update({ecs_params.SERVICE_HOSTNAME_T: service.hostname})
        service.dependencies.append(ecs_params.LOG_GROUP_T)
        # ServiceStack(
        #         ecs_service.resource_name,
        #         template=ecs_service.template,
        #         ecs_service=ecs_service,
        #         Parameters=ecs_service.parameters,
        #         DependsOn=ecs_service.dependencies,
        #         **kwargs,
        #     )
        # )
        LOG.debug(f"Service {service_name} added.")
        services[service_name] = service
    return services
