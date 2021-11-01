#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import FindInMap, GetAtt, Ref
from troposphere.ec2 import SecurityGroupIngress
from troposphere.iam import PolicyType

from ecs_composex.common import add_parameters, setup_logging
from ecs_composex.common.cfn_params import Parameter
from ecs_composex.common.services_helpers import extend_container_envvars
from ecs_composex.ecs.ecs_iam import define_service_containers
from ecs_composex.ecs.ecs_params import SG_T
from ecs_composex.opensearch.opensearch_params import (
    MAPPINGS_KEY,
    OS_DOMAIN_ARN,
    OS_DOMAIN_ENDPOINT,
    OS_DOMAIN_ID,
    OS_DOMAIN_PORT,
    OS_DOMAIN_SG,
    RES_KEY,
)
from ecs_composex.resource_settings import (
    generate_resource_permissions_statements,
    get_parameter_settings,
    get_selected_services,
    handle_resource_to_services,
)
from ecs_composex.tcp_resources_settings import handle_new_tcp_resource

LOG = setup_logging()


def map_service_perms_to_resource(
    resource,
    statement,
    policies,
    family,
    services,
    access_type,
    arn_value,
):
    """
    Function to
    :param resource:
    :param ecs_composex.common.compose_services.ComposeFamily family:
    :param services:
    :param str access_type:
    :param arn_value: The value for main attribute, used for env vars
    :return:
    """
    res_perms = generate_resource_permissions_statements(
        resource.logical_name, policies, arn=arn_value, ignore_missing_primary=True
    )
    containers = define_service_containers(family.template)
    policy = res_perms[access_type]
    statement.append(policy)
    for container in containers:
        for service in services:
            if container.Name == service.name:
                LOG.debug(f"Extended env vars for {container.Name} -> {service.name}")
                extend_container_envvars(container, resource.env_vars)


def add_security_group_ingress(target_family, resource, sg_id, port):
    """
    Function to add a SecurityGroupIngress rule into the ECS Service template

    :param ecs_composex.common.compose_services.ComposeFamily target_family:
    :param ecs_composex.ecs.ServicesStack service_stack: The root stack for the services
    :param str db_name: the name of the database to use for imports
    :param sg_id: The security group Id to use for ingress. DB Security group, not service's
    :param port: The port for Ingress to the DB.
    """
    if isinstance(sg_id, Parameter):
        add_parameters(
            target_family.template,
            [
                resource.attributes_outputs[OS_DOMAIN_SG]["ImportParameter"],
                resource.attributes_outputs[OS_DOMAIN_PORT]["ImportParameter"],
            ],
        )
        target_family.stack.Parameters.update(
            {
                resource.attributes_outputs[OS_DOMAIN_SG][
                    "ImportParameter"
                ].title: resource.attributes_outputs[OS_DOMAIN_SG]["ImportValue"],
                resource.attributes_outputs[OS_DOMAIN_PORT][
                    "ImportParameter"
                ].title: resource.attributes_outputs[OS_DOMAIN_PORT]["ImportValue"],
            }
        )
        res_sg = Ref(sg_id)
        res_port = Ref(port)
    elif isinstance(sg_id, FindInMap):
        res_port = port
        res_sg = sg_id
    else:
        raise TypeError(
            "The sg_id must be one one of", (Parameter, FindInMap), "Got", type(sg_id)
        )
    rule = SecurityGroupIngress(
        f"AllowFrom{target_family.logical_name}to{resource.logical_name}",
        GroupId=res_sg,
        FromPort=res_port,
        ToPort=res_port,
        Description=f"Allow FROM {target_family.logical_name} TO {resource.logical_name}",
        SourceSecurityGroupId=GetAtt(target_family.template.resources[SG_T], "GroupId"),
        SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
        IpProtocol="6",
    )
    if rule.title not in target_family.template.resources:
        target_family.template.add_resource(rule)


def map_resource_to_service_family(
    resource, target, arn_attr, statement, selected_services, settings
):
    """
    Associates the resource to the service family

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain resource:
    :param tuple target:
    :param statement:
    :param arn_attr: The pointer to the ARN definition of the resource
    :param list selected_services:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if resource.mapping_key not in target[0].template.mappings and keyisset(
        resource.mapping_key, settings.mappings
    ):
        target[0].template.add_mapping(
            resource.mapping_key, settings.mappings[resource.mapping_key]
        )
    if keyisset("Http", target[3]):
        map_service_perms_to_resource(
            resource,
            statement,
            resource.policies_scaffolds["Http"],
            target[0],
            selected_services,
            target[3]["Http"],
            arn_value=arn_attr,
        )
    if keyisset("IAM", target[3]):
        map_service_perms_to_resource(
            resource,
            statement,
            resource.policies_scaffolds["IAM"],
            target[0],
            selected_services,
            target[3]["IAM"],
            arn_value=arn_attr,
        )
    if keyisset(OS_DOMAIN_SG.return_value, resource.mappings):
        resource.add_new_output_attribute(
            OS_DOMAIN_SG,
            (
                f"{resource.logical_name}{OS_DOMAIN_SG.return_value}",
                resource.security_group,
                GetAtt,
                OS_DOMAIN_SG.return_value,
            ),
        )
        resource.add_new_output_attribute(
            OS_DOMAIN_PORT,
            (
                f"{resource.logical_name}{OS_DOMAIN_PORT.return_value}",
                OS_DOMAIN_PORT,
                Ref,
                None,
            ),
        )
        resource.generate_outputs()
        add_security_group_ingress(
            target[0],
            resource,
            resource.attributes_outputs[OS_DOMAIN_SG]["ImportValue"],
            resource.attributes_outputs[OS_DOMAIN_PORT]["ImportValue"],
        )


def handle_lookup_to_service_mapping(res_name, resource, settings):
    """

    :param str res_name:
    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain resource:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if not resource.output_properties:
        resource.init_outputs()
    if not resource.attributes_outputs:
        resource.generate_outputs()
    resource.generate_resource_envvars()
    for target in resource.families_targets:
        statement = []
        iam_policy = PolicyType(
            MAPPINGS_KEY,
            Roles=[Ref(target[0].task_role.name["ImportParameter"])],
            PolicyName=MAPPINGS_KEY,
            PolicyDocument={"Version": "2012-10-17", "Statement": statement},
        )
        if iam_policy.title not in target[0].template.resources:
            target[0].template.add_resource(iam_policy)
        else:
            statement = getattr(
                target[0].template.resources[iam_policy.title], "PolicyDocument"
            )["Statement"]
        selected_services = get_selected_services(resource, target)
        if selected_services:
            arn_attr = resource.attributes_outputs[OS_DOMAIN_ARN]["ImportValue"]
            map_resource_to_service_family(
                resource, target, arn_attr, statement, selected_services, settings
            )


def assign_new_resource_to_service(
    resource, res_root_stack, settings, arn_parameter, parameters=None
):
    """
    Function to assign the new resource to the service/family using it.

    :param resource: The resource
    :type resource: ecs_composex.common.compose_resources.XResource
    :param res_root_stack: The root stack of the resource type
    :type res_root_stack: ecs_composex.common.stacks.ComposeXStack
    :param: The parameter mapping to the ARN attribute of the resource
    :type arn_parameter: ecs_composex.common.cfn_parameter.Parameter arn_parameter
    """
    if parameters is None:
        parameters = []
    arn_settings = get_parameter_settings(resource, arn_parameter)
    extra_settings = [get_parameter_settings(resource, param) for param in parameters]
    params_to_add = [arn_settings[1]]
    params_values = {arn_settings[0]: arn_settings[2]}
    for setting in extra_settings:
        params_to_add.append(setting[1])
        params_values[setting[0]] = setting[2]
    for target in resource.families_targets:
        selected_services = get_selected_services(resource, target)
        statement = []
        iam_policy = PolicyType(
            MAPPINGS_KEY,
            Roles=[Ref(target[0].task_role.name["ImportParameter"])],
            PolicyName=MAPPINGS_KEY,
            PolicyDocument={"Version": "2012-10-17", "Statement": statement},
        )
        if iam_policy.title not in target[0].template.resources:
            target[0].template.add_resource(iam_policy)
        else:
            statement = getattr(
                target[0].template.resources[iam_policy.title], "PolicyDocument"
            )["Statement"]
        if selected_services:
            add_parameters(target[0].template, params_to_add)
            target[0].stack.Parameters.update(params_values)
            map_resource_to_service_family(
                resource,
                target,
                Ref(arn_settings[1]),
                statement,
                selected_services,
                settings,
            )
            if res_root_stack.title not in target[0].stack.DependsOn:
                target[0].stack.DependsOn.append(res_root_stack.title)


def opensearch_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to associate permissions from the IAM service to OpenSearch domain

    :param dict resources: The resources to associate
    :param ecs_composex.common.stacks.ComposeXStack services_stack:
    :param ecs_composex.common.stacks.ComposeXStack res_root_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    if res_root_stack.is_void:
        LOG.info(f"{RES_KEY} - No new resources to create")
    for res_name, resource in resources.items():
        if (
            not res_root_stack.is_void
            and resource.cfn_resource
            and not resource.mappings
        ):
            if resource.security_group:
                handle_new_tcp_resource(
                    resource,
                    res_root_stack,
                    port_parameter=OS_DOMAIN_PORT,
                    sg_parameter=OS_DOMAIN_SG,
                )
            assign_new_resource_to_service(
                resource,
                res_root_stack,
                settings,
                arn_parameter=OS_DOMAIN_ARN,
                parameters=[OS_DOMAIN_ENDPOINT, OS_DOMAIN_ID],
            )
        elif resource.mappings:
            handle_lookup_to_service_mapping(res_name, resource, settings)
