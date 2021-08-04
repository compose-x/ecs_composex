#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module of functions factorizing common patterns for TCP based access such as RDS, DocumentDB
"""

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import FindInMap, GetAtt, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import Secret as EcsSecret
from troposphere.iam import PolicyType

from ecs_composex.common import LOG, add_parameters
from ecs_composex.common.compose_resources import get_parameter_settings
from ecs_composex.common.services_helpers import extend_container_secrets
from ecs_composex.ecs.ecs_params import EXEC_ROLE_T, SG_T, TASK_ROLE_T
from ecs_composex.rds.rds_params import DB_SECRET_POLICY_NAME


def define_db_prefix(db, mappings_definition):
    prefix = ""
    if keypresent("PrefixWithDbName", mappings_definition):
        if isinstance(mappings_definition["PrefixWithDbName"], bool):
            prefix = (
                f"{db.name}_"
                if keyisset("PrefixWithDbName", mappings_definition)
                else ""
            )
        elif isinstance(mappings_definition["PrefixWithDbName"], str):
            prefix = f"{mappings_definition['PrefixWithDbName']}_"
        else:
            raise TypeError(
                "PrefixWithDbName can only be one of",
                str,
                bool,
                "Got",
                type(mappings_definition["PrefixWithDbName"]),
            )
    return prefix


def define_secrets_keys_mappings(mappings_definition):
    """
    Function to analyze the secrets mapping provided

    :param mappings_definition:
    :return:
    """
    rendered_mappings = []
    mappings = mappings_definition["Mappings"]
    if isinstance(mappings, list):
        for mapping in mappings:
            if not keyisset("SecretKey", mapping):
                raise KeyError(
                    "When using a list of mappings, you must specify at least SecretKey. Got",
                    mapping.keys(),
                )
            if not keyisset("VarName", mapping):
                mapping["VarName"] = mapping["SecretKey"]
            rendered_mappings.append(mapping)
    elif isinstance(mappings, dict):
        for key, value in mappings.items():
            mapping = {"SecretKey": key, "VarName": value}
            rendered_mappings.append(mapping)
    return rendered_mappings


def generate_secrets_from_secrets_mappings(
    db, secrets_list, secret_definition, mappings_definition
):
    """
    Function to generate a list of EcsSecrets

    :param ecs_composex.common.compose_resources.Rds db: the RDS DB object
    :param list secrets_list:
    :param secret_definition:
    :param mappings_definition:
    :return:
    """
    if not keyisset("Mappings", mappings_definition):
        raise KeyError("You must specify a Mappings list for secrets")
    elif not isinstance(mappings_definition["Mappings"], (dict, list)):
        raise TypeError("Secrets Mappings must be a list of key/value dictionary")
    prefix = define_db_prefix(db, mappings_definition)
    mappings_list = define_secrets_keys_mappings(mappings_definition)
    for secret in mappings_list:
        if isinstance(secret_definition, Ref):
            param_name = secret_definition.data["Ref"]
            secret_from = Sub(f"${{{param_name}}}:{secret['SecretKey']}::")
        elif isinstance(secret_definition, FindInMap):
            secret_from = Sub(
                f"${{SecretArn}}:{secret['SecretKey']}::", SecretArn=secret_definition
            )
        else:
            raise TypeError(
                "secret_definition must be one of",
                FindInMap,
                Ref,
                "Got",
                type(secret_definition),
            )
        secrets_list.append(
            EcsSecret(Name=f"{prefix}{secret['VarName']}", ValueFrom=secret_from)
        )


def define_db_secrets(db, secret_import, target_definition):
    """
    Function to return the list of env vars set for the DB to use as env vars for the Secret.

    :return: list of names to use.
    :rtype: list
    """
    secrets = []
    if keyisset("SecretsMappings", target_definition[-1]):
        LOG.info(f"{target_definition[-1]['name']} expects specific name for {db.name}")
        generate_secrets_from_secrets_mappings(
            db, secrets, secret_import, target_definition[-1]["SecretsMappings"]
        )
    elif keyisset("SecretsMappings", db.settings):
        LOG.info(f"{db.name} has specific secrets mappings settings")
        generate_secrets_from_secrets_mappings(
            db, secrets, secret_import, db.settings["SecretsMappings"]
        )
    elif keyisset("EnvNames", db.settings):
        for name in db.settings["EnvNames"]:
            secrets.append(EcsSecret(Name=name, ValueFrom=secret_import))
    if db.name not in [s.Name for s in secrets]:
        secrets.append(EcsSecret(Name=db.name, ValueFrom=secret_import))
    return secrets


def add_secret_to_container(db, secret_import, service, target_definition):
    """
    Function to add DB secret to container

    :param ecs_composex.common.compose_resources.Rds db: the RDS DB object
    :param service: The target service definition
    :param str,AWSHelper secret_import: secret arn
    :param target_definition:
    """
    db_secrets = define_db_secrets(db, secret_import, target_definition)
    for db_secret in db_secrets:
        extend_container_secrets(service.container_definition, db_secret)


def add_security_group_ingress(service_stack, db_name, sg_id, port):
    """
    Function to add a SecurityGroupIngress rule into the ECS Service template

    :param ecs_composex.ecs.ServicesStack service_stack: The root stack for the services
    :param str db_name: the name of the database to use for imports
    :param sg_id: The security group Id to use for ingress. DB Security group, not service's
    :param port: The port for Ingress to the DB.
    """
    service_template = service_stack.stack_template
    SecurityGroupIngress(
        f"AllowFrom{service_stack.title}to{db_name}",
        template=service_template,
        GroupId=sg_id,
        FromPort=port,
        ToPort=port,
        Description=Sub(f"Allow FROM {service_stack.title} TO {db_name}"),
        SourceSecurityGroupId=GetAtt(service_template.resources[SG_T], "GroupId"),
        SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
        IpProtocol="6",
    )


def generate_rds_secrets_permissions(resources, db_name):
    """
    Function to generate the IAM policy to use for the ECS Execution role to get access to the RDS secrets
    :return:
    """
    return {
        "Sid": f"AccessTo{db_name}Secret",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue", "secretsmanager:GetSecret"],
        "Resource": resources,
    }


def add_secrets_access_policy(
    service_template, secret_import, db_name, use_task_role=False
):
    """
    Function to add or append policy to access DB Secret for the Execution Role

    :param service_template:
    :param secret_import:
    :return:
    """
    db_policy_statement = generate_rds_secrets_permissions(secret_import, db_name)
    task_role = service_template.resources[TASK_ROLE_T]
    exec_role = service_template.resources[EXEC_ROLE_T]
    if keyisset(DB_SECRET_POLICY_NAME, service_template.resources):
        db_policy = service_template.resources[DB_SECRET_POLICY_NAME]
        db_policy.PolicyDocument["Statement"].append(db_policy_statement)
        if use_task_role:
            db_policy.Roles.append(Ref(task_role))
    else:
        policy = PolicyType(
            DB_SECRET_POLICY_NAME,
            template=service_template,
            Roles=[Ref(exec_role)],
            PolicyName=DB_SECRET_POLICY_NAME,
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [db_policy_statement],
            },
        )
        if use_task_role:
            policy.Roles.append(Ref(task_role))


def handle_db_secret_to_services(db, secret_import, target):
    valid_ones = [
        service for service in target[2] if service not in target[0].ignored_services
    ]
    for service in valid_ones:
        add_secret_to_container(db, secret_import, service, target)
    add_secrets_access_policy(target[0].template, secret_import, db.logical_name)


def handle_new_dbs_to_services(db, sg_import, target, port=None):
    add_security_group_ingress(
        target[0].stack, db.logical_name, sg_id=sg_import, port=port
    )


def handle_new_tcp_resource(
    resource, res_root_stack, port_parameter, sg_parameter, secret_parameter=None
):
    """
    Funnction to standardize TCP services access from services.

    :param resource:
    :param res_root_stack:
    :param port_parameter:
    :param sg_parameter:
    :param secret_parameter:
    :return:
    """
    if resource.logical_name not in res_root_stack.stack_template.resources:
        raise KeyError(
            f"DB {resource.logical_name} not defined in {res_root_stack.title} root template"
        )

    parameters_to_add = []
    parameters_values = {}

    port_settings = get_parameter_settings(resource, port_parameter)
    parameters_to_add.append(port_settings[1])
    parameters_values[port_settings[0]] = port_settings[2]

    sg_settings = get_parameter_settings(resource, sg_parameter)
    parameters_to_add.append(sg_settings[1])
    parameters_values[sg_settings[0]] = sg_settings[2]

    for target in resource.families_targets:
        add_parameters(target[0].template, parameters_to_add)
        target[0].stack.Parameters.update(parameters_values)
        handle_new_dbs_to_services(
            resource, Ref(sg_settings[1]), target, port=Ref(port_settings[1])
        )
        if secret_parameter:
            secret_settings = get_parameter_settings(resource, secret_parameter)
            add_parameters(target[0].template, [secret_settings[1]])
            target[0].stack.Parameters.update({secret_settings[0]: secret_settings[2]})
            handle_db_secret_to_services(resource, Ref(secret_settings[1]), target)
        if res_root_stack.title not in target[0].stack.DependsOn:
            target[0].stack.DependsOn.append(res_root_stack.title)
