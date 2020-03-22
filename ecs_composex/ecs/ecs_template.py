# -*- coding: utf-8 -*-
""" Core ECS Template building """

from troposphere import Ref, Sub, Tags
from troposphere.cloudformation import Stack
from troposphere.ec2 import SecurityGroup
from troposphere.logs import LogGroup

from ecs_composex.common import LOG
from ecs_composex.common import (
    cfn_params, build_template, KEYISSET
)
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    ROOT_STACK_NAME
)
from ecs_composex.ecs import ecs_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, CLUSTER_NAME_T
from ecs_composex.ecs.ecs_service import (
    generate_service_template
)
from ecs_composex.vpc import vpc_params


def validate_labels(service_labels):
    """
    Function to validate service labels
    # TO IMPLEMENT
    """
    return True


def validate_input(services):
    """
    Validates services docker format
    """
    props_must_have = [
        'image'
    ]
    for service_name in services:
        service = services[service_name]
        for prop in props_must_have:
            if not KEYISSET(prop, service):
                raise KeyError('Service {service_name} is missing property {prop}')
        if prop == 'labels':
            assert validate_labels(service[prop])
    return True


def add_clusterwide_security_group(template):
    """
    Function to generate the service Load Balancers (if Any)
    """
    sg = SecurityGroup(
        'ClusterWideSecurityGroup',
        template=template,
        GroupDescription=Sub(f"SG for ${{{CLUSTER_NAME_T}}}"),
        GroupName=Sub(f"cluster-${{{CLUSTER_NAME_T}}}"),
        Tags=Tags(
            {
                'Name': Sub(f"clustersg-${{{CLUSTER_NAME_T}}}"),
                'ClusterName': Ref(CLUSTER_NAME)
            }
        ),
        VpcId=Ref(vpc_params.VPC_ID)
    )
    return sg


def add_services_stacks(compose_content, root_tpl, cluster_sg, session=None, **kwargs):
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
    for service_name in compose_content[ecs_params.RES_KEY]:
        service = compose_content[ecs_params.RES_KEY][service_name]
        service_set = generate_service_template(
            compose_content,
            service_name,
            service,
            session=session,
            **kwargs
        )
        parameters = {
            CLUSTER_NAME_T: Ref(CLUSTER_NAME),
            ROOT_STACK_NAME_T: Ref(ROOT_STACK_NAME),
            ecs_params.CLUSTER_SG_ID_T: Ref(cluster_sg)
        }
        dependencies = [ecs_params.LOG_GROUP_T]
        LOG.debug(service_set[-1])
        if isinstance(service_set[-1], list):
            dependencies = dependencies + service_set[-1]
        LOG.debug(dependencies)
        parameters.update(service_set[1])
        if service_set[0]:
            Stack(
                service_name,
                template=root_tpl,
                TemplateURL=service_set[0],
                Parameters=parameters,
                DependsOn=dependencies
            )
        else:
            Warning(
                f"Template for service {service_name}"
                "was not successfully generated"
            )
        LOG.debug(f"Service {service_name} added.")
        LOG.info(f"Template URL: {service_set[0]}")


def generate_services_templates(compose_content, session=None, **kwargs):
    """
    Function to generate the root template
    """
    parameters = [
        cfn_params.SERVICE_DISCOVERY,
        CLUSTER_NAME,
        vpc_params.VPC_ID,
        vpc_params.PUBLIC_SUBNETS,
        vpc_params.APP_SUBNETS
    ]
    template = build_template(
        'Root template for ECS Services',
        parameters
    )

    template.add_resource(LogGroup(
        ecs_params.LOG_GROUP_T,
        RetentionInDays=30,
        LogGroupName=Ref(CLUSTER_NAME)
    ))
    cluster_sg = add_clusterwide_security_group(template)
    add_services_stacks(compose_content, template, cluster_sg, session=session, **kwargs)
    if KEYISSET('Debug', kwargs):
        with open('/tmp/ecs_root.json', 'w') as services_fd:
            services_fd.write(template.to_json())
    return template
