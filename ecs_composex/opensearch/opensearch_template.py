#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


"""
OpenSearch module to manage creation of new OpenSearch domains
"""
import re

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub, Tags, opensearchservice
from troposphere.ec2 import SecurityGroup

from ecs_composex.common import add_outputs, add_parameters, setup_logging
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.opensearch.opensearch_params import OS_DOMAIN_SG
from ecs_composex.resources_import import import_record_properties
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID

LOG = setup_logging()


def validate_security_groups(domain, groups):
    valid = True
    for group in groups:
        if not isinstance(group, str):
            valid = False
            LOG.error(f"{domain.name} - Group {group} is not of type <str>")
            break
        elif isinstance(group, str) and not re.match(r"sg-[a-z0-9]+", group):
            valid = False
            LOG.error(
                f"{domain.name} - Group {group} is not valid as pert (sg-[a-z0-9]+)"
            )
            break
    if not valid:
        raise ValueError(
            f"{domain.name} has SecurityGroupIds set but are not valid.", groups
        )


def define_domain_security_group(domain, stack):
    """
    Create a new Security Group for the Domain

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    :return: The security Group
    """
    add_parameters(stack.stack_template, [VPC_ID])
    sg = SecurityGroup(
        f"{domain.logical_name}VPCSecurityGroup",
        GroupDescription=Sub(
            f"{domain.logical_name} OpenSearch SG in ${{STACK_NAME}}",
            STACK_NAME=define_stack_name(stack.stack_template),
        ),
        VpcId=Ref(VPC_ID),
        Tags=Tags(OsDomainName=domain.name),
    )
    stack.stack_template.add_resource(sg)
    return sg


def add_new_security_group(domain, properties, stack):
    """
    Function to create a new Security Group
    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict properties:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    """
    if keyisset("VPCOptions", properties) and keyisset(
        "SecurityGroupIds", properties["VPCOptions"]
    ):
        groups = properties["VPCOptions"]["SecurityGroupIds"]
        validate_security_groups(domain, groups)
        LOG.warn(
            f"{domain.name} already has SecurityGroupIds set. Cannot verify its validity"
        )
        LOG.info(
            f"{domain.name} has already SecurityGroupIds set. "
            "Adding a new one for the purpose of Compose-X Automation"
        )
        domain.security_group = define_domain_security_group(domain, stack)
        properties["VPCOptions"]["SecurityGroupIds"].append(Ref(domain.security_group))
    elif (
        keyisset("VPCOptions", properties)
        and not keyisset("SecurityGroupIds", properties["VPCOptions"])
    ) or (domain.settings and keyisset("Subnets", domain.settings)):
        domain.security_group = define_domain_security_group(domain, stack)
        vpc_options = {
            "SecurityGroupIds": [Ref(domain.security_group)],
            "SubnetIds": Ref(domain.subnets_override)
            if domain.subnets_override
            else Ref(STORAGE_SUBNETS),
        }
        properties["VPCOptions"] = opensearchservice.VPCOptions(**vpc_options)


def create_new_domains(new_domains, stack):
    """
    Function to create the new CFN Template for the OS Domains to create

    :param list[ecs_composex.opensearch.opensearch_stack.OpenSearchDomain] new_domains:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    """
    for domain in new_domains:
        domain.set_override_subnets()
        props = import_record_properties(domain.properties, opensearchservice.Domain)
        if keyisset("VPCOptions", props) or domain.subnets_override:
            add_new_security_group(domain, props, stack)
        domain.cfn_resource = opensearchservice.Domain(domain.logical_name, **props)
        stack.stack_template.add_resource(domain.cfn_resource)
        domain.init_outputs()
        if domain.security_group:
            domain.output_properties.update(
                {
                    OS_DOMAIN_SG: (
                        f"{domain.logical_name}{OS_DOMAIN_SG.return_value}",
                        domain.security_group,
                        GetAtt,
                        OS_DOMAIN_SG.return_value,
                    )
                }
            )
        domain.generate_outputs()
        domain.generate_resource_envvars()
        add_outputs(stack.stack_template, domain.outputs)
