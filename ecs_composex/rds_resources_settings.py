# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module of functions factorizing common patterns for TCP based access such as RDS, DocumentDB
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily
    from ecs_composex.common.cfn_params import Parameter
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.compose.x_resources.network_x_resources import (
        NetworkXResource,
        DatabaseXResource,
    )
    from ecs_composex.common.stacks import ComposeXStack

from botocore.exceptions import ClientError
from compose_x_common.aws import get_account_id
from compose_x_common.aws.rds import RDS_DB_ID_CLUSTER_ARN_RE
from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from troposphere import FindInMap, GetAtt, Ref, Sub
from troposphere.ec2 import SecurityGroupIngress
from troposphere.ecs import Environment
from troposphere.ecs import Secret as EcsSecret
from troposphere.iam import PolicyType

from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_resource, add_update_mapping
from ecs_composex.compose.compose_services.helpers import (
    extend_container_envvars,
    extend_container_secrets,
)
from ecs_composex.ecs.ecs_params import SG_T
from ecs_composex.rds.rds_params import DB_SECRET_POLICY_NAME


def filter_out_tag_resources(lookup_attributes, rds_resource, tagging_api_id):
    """
    Function to return the ClusterARN to use out of multiple found when using GroupTaggingAPI
    :param dict lookup_attributes:
    :param rds_resource:
    :param str tagging_api_id:
    :return: The cluster ARN to use
    :rtype: str
    :raises: LookupError
    """
    clusters = find_aws_resource_arn_from_tags_api(
        lookup_attributes, rds_resource.lookup_session, tagging_api_id, allow_multi=True
    )
    if isinstance(clusters, str):
        return clusters
    elif isinstance(clusters, list):
        if len(clusters) == 1:
            rds_resource.arn = clusters[0]
        if len(clusters) >= 2:
            cluster_arns = [
                arn for arn in clusters if RDS_DB_ID_CLUSTER_ARN_RE.match(arn)
            ]
            if len(cluster_arns) > 1:
                raise LookupError(
                    "There is more than one RDS cluster found with the given Lookup details",
                    cluster_arns,
                )
            return cluster_arns[0]


def lookup_rds_secret(rds_resource, secret_lookup):
    """
    Lookup RDS DB Secret specified

    :param ecs_composex.compose.x_resources.network_x_resources.DatabaseXResource rds_resource:
    :param secret_lookup:
    :return:
    """
    if keyisset("Arn", secret_lookup):
        client = rds_resource.lookup_session.client("secretsmanager")
        try:
            secret_arn = client.describe_secret(SecretId=secret_lookup["Arn"])["ARN"]

        except client.exceptions.ResourceNotFoundException:
            LOG.error(
                f"{rds_resource.module.res_key}.{rds_resource.name}"
                f" - Secret {secret_lookup['Arn']} not found"
            )
            raise
        except ClientError as error:
            LOG.error(error)
            raise
    elif keyisset("Tags", secret_lookup):
        secret_arn = find_aws_resource_arn_from_tags_api(
            rds_resource.lookup["secret"],
            rds_resource.lookup_session,
            "secretsmanager:secret",
        )
    else:
        raise LookupError(
            f"{rds_resource.module.res_key}.{rds_resource.name}"
            " - Failed to find the DB Secret"
        )
    if secret_arn:
        rds_resource.lookup_properties[
            rds_resource.db_secret_arn_parameter
        ] = secret_arn


def lookup_rds_resource(
    rds_resource,
    arn_re,
    native_lookup_function,
    cfn_resource_type,
    tagging_api_id,
    subattribute_key=None,
):
    """

    :param rds_resource:
    :param arn_re:
    :param native_lookup_function:
    :param cfn_resource_type:
    :param tagging_api_id:
    :param subattribute_key:
    :return:
    """
    lookup_attributes = rds_resource.lookup
    if subattribute_key is not None:
        lookup_attributes = rds_resource.lookup[subattribute_key]
    if keyisset("Arn", lookup_attributes):
        arn_parts = arn_re.match(lookup_attributes["Arn"])
        if not arn_parts:
            raise KeyError(
                f"{rds_resource.module.res_key}.{rds_resource.name} - "
                f"ARN {lookup_attributes['Arn']} is not valid. Must match",
                arn_re.pattern,
            )
        rds_resource.arn = lookup_attributes["Arn"]
        resource_id = arn_parts.group("id")
        account_id = arn_parts.group("accountid")
    elif keyisset("Tags", lookup_attributes):
        rds_resource.arn = filter_out_tag_resources(
            lookup_attributes, rds_resource, tagging_api_id
        )

        arn_parts = arn_re.match(rds_resource.arn)
        resource_id = arn_parts.group("id")
        account_id = arn_parts.group("accountid")
    else:
        raise KeyError(
            f"{rds_resource.module.res_key}.{rds_resource.name} - "
            "You must specify Arn or Tags to identify existing resource"
        )
    if not rds_resource.arn:
        raise LookupError(
            f"{rds_resource.module.res_key}.{rds_resource.name}"
            " - Failed to find the AWS Resource with given tags"
        )
    props = {}
    _account_id = get_account_id(rds_resource.lookup_session)
    if _account_id == account_id and rds_resource.cloud_control_attributes_mapping:
        props = rds_resource.cloud_control_attributes_mapping_lookup(
            cfn_resource_type, resource_id
        )
    if not props:
        props = rds_resource.native_attributes_mapping_lookup(
            account_id, resource_id, native_lookup_function
        )
    rds_resource.lookup_properties = props
    rds_resource.generate_cfn_mappings_from_lookup_properties()


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
                    "When using a list of mappings, "
                    "you must specify at least SecretKey. Got",
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
                f"${{SecretArn}}:{secret['SecretKey']}::",
                SecretArn=secret_definition,
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


def define_db_secrets(db: DatabaseXResource, secret_import, target: tuple) -> list:
    """
    Function to return the list of env vars set for the DB to use as env vars for the Secret.

    :return: list of names to use.
    :rtype: list
    """
    secrets = []
    if keyisset("DoNotExposeMappings", target[-1]):
        LOG.warning(
            f"{db.module.res_key}.{db.name} - {target[0].name} - "
            "DoNotExposeMappings set. Not creating secret mappings"
        )
        return secrets
    if keyisset("SecretsMappings", target[-1]):
        LOG.info(f"{target[0].name} expects specific name for {db.name}")
        generate_secrets_from_secrets_mappings(
            db, secrets, secret_import, target[-1]["SecretsMappings"]
        )
    elif keyisset("SecretsMappings", db.settings):
        LOG.info(f"{db.module.res_key}.{db.name} has secrets mappings settings.")
        generate_secrets_from_secrets_mappings(
            db, secrets, secret_import, db.settings["SecretsMappings"]
        )
    else:
        LOG.info(
            f"{db.module.res_key}.{db.name}"
            " - No SecretsMappings set. Exposing the secrets content as-is."
        )
        secrets.append(EcsSecret(Name=db.name, ValueFrom=secret_import))
    return secrets


def add_secret_to_container(db, secret_import, service, target):
    """
    Function to add DB secret to container

    :param ecs_composex.common.compose_resources.Rds db: the RDS DB object
    :param service: The target service definition
    :param str,AWSHelper secret_import: secret arn
    :param tuple target:
    """
    db_secrets = define_db_secrets(db, secret_import, target)
    for db_secret in db_secrets:
        extend_container_secrets(service.container_definition, db_secret)


def add_security_group_ingress(service_stack: ComposeXStack, db_name: str, sg_id, port):
    """
    Function to add a SecurityGroupIngress rule into the ECS Service template

    :param ecs_composex.ecs.ServicesStack service_stack: The root stack for the services
    :param str db_name: the name of the database to use for imports
    :param sg_id: The security group Id to use for ingress. DB Security group, not service's
    :param port: The port for Ingress to the DB.
    """
    add_resource(
        service_stack.stack_template,
        SecurityGroupIngress(
            f"AllowFrom{service_stack.title}to{db_name}",
            GroupId=sg_id,
            FromPort=port,
            ToPort=port,
            Description=Sub(f"Allow FROM {service_stack.title} TO {db_name}"),
            SourceSecurityGroupId=GetAtt(
                service_stack.stack_template.resources[SG_T], "GroupId"
            ),
            SourceSecurityGroupOwnerId=Ref("AWS::AccountId"),
            IpProtocol="6",
        ),
    )


def generate_rds_secrets_permissions(resources, db_name: str) -> dict:
    """
    Function to generate the IAM policy to use for the ECS Execution role to get access to the RDS secrets
    :return:
    """
    return {
        "Sid": f"AccessTo{db_name}Secret",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue", "secretsmanager:GetSecret"],
        "Resource": resources if isinstance(resources, list) else [resources],
    }


def add_secrets_access_policy(
    target: tuple,
    secret_import,
    db,
    use_task_role: Union[bool, dict] = False,
):
    """
    Function to add or append policy to access DB Secret for the Execution Role

    :param tuple target:
    :param secret_import:
    :return:
    """
    service_family = target[0]
    db_policy_statement = generate_rds_secrets_permissions(
        secret_import, db.logical_name
    )
    task_role = service_family.iam_manager.task_role.name
    exec_role = service_family.iam_manager.exec_role.name
    if keyisset(DB_SECRET_POLICY_NAME, service_family.template.resources):
        policy = service_family.template.resources[DB_SECRET_POLICY_NAME]
        policy.PolicyDocument["Statement"].append(db_policy_statement)
    else:
        policy = PolicyType(
            DB_SECRET_POLICY_NAME,
            template=service_family.template,
            Roles=[exec_role],
            PolicyName=DB_SECRET_POLICY_NAME,
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [db_policy_statement],
            },
        )
    if use_task_role:
        handle_task_role_access(
            use_task_role, policy, secret_import, task_role, db, service_family
        )


def handle_task_role_access(
    use_task_role: Union[dict, bool],
    policy: PolicyType,
    secret_import,
    task_role,
    db: DatabaseXResource,
    family: ComposeFamily,
) -> None:
    if policy.Roles and task_role not in policy.Roles:
        policy.Roles.append(task_role)
    if isinstance(use_task_role, dict):
        secret_env_key = use_task_role["SecretEnvName"]
    elif isinstance(use_task_role, bool):
        secret_env_key = f"{db.logical_name}_SECRET"
    else:
        raise TypeError(
            "use_task_role must be one of",
            (bool, dict),
            "Got",
            use_task_role,
            type(use_task_role),
        )
    add_secret_arn_env_var(family, secret_env_key, secret_import)
    LOG.info(
        f"{db.module.res_key}.{db.name} - Added {secret_env_key} environment variable to the DB Secret."
        "Granted access to the Task Role"
    )


def add_secret_arn_env_var(
    family: ComposeFamily, secret_env_key: str, secret_definition
):
    """
    Adds environment variable to service, using the Name/ARN of the service as value

    :param family:
    :param secret_env_key:
    :param secret_definition:
    :return:
    """
    if isinstance(secret_definition, list):
        raise TypeError("secret_definition cannot be a list. Got", secret_definition)
    for service in family.services:
        if service.is_aws_sidecar:
            continue
        extend_container_envvars(
            service.container_definition,
            [Environment(Name=secret_env_key, Value=secret_definition)],
        )


def handle_db_secret_to_services(
    db: DatabaseXResource | NetworkXResource, secret_import, target: tuple
) -> None:
    """
    Maps DB Secret to ECS Service containers. It however won't expose the secret to an AWS SideCar (i.e. x-ray).

    :param ecs_composex.compose.x_resources.network_x_resources.DatabaseXResource db:
    :param troposphere.AWSHelperFn secret_import: The pointer to the Secret
    :param tuple target: The family target
    """
    for service in target[2]:
        if service not in target[0].ordered_services or service.is_aws_sidecar:
            continue
        add_secret_to_container(db, secret_import, service, target)
    grant_task_role_access = set_else_none(
        "GrantTaskAccess", target[-1], alt_value=False
    )
    add_secrets_access_policy(target, secret_import, db, grant_task_role_access)


def handle_import_dbs_to_services(
    db: DatabaseXResource | NetworkXResource, target: tuple
) -> None:
    """
    Function to map the Looked up DBs (DocDB and RDS) to the services.
    """
    if db.db_secret_arn_parameter and keyisset(
        db.db_secret_arn_parameter, db.attributes_outputs
    ):
        valid_ones = [
            service for service in target[2] if service in target[0].ordered_services
        ]
        for service in valid_ones:
            add_secret_to_container(
                db,
                db.attributes_outputs[db.db_secret_arn_parameter]["ImportValue"],
                service,
                target,
            )
        grant_task_role_access = set_else_none(
            "GrantTaskAccess", target[-1], alt_value=False
        )
        add_secrets_access_policy(
            target,
            db.attributes_outputs[db.db_secret_arn_parameter]["ImportValue"],
            db,
            use_task_role=grant_task_role_access,
        )
    add_security_group_ingress(
        target[0].stack,
        db.logical_name,
        sg_id=db.attributes_outputs[db.security_group_param]["ImportValue"],
        port=db.attributes_outputs[db.port_param]["ImportValue"],
    )


def import_dbs(
    db: NetworkXResource | DatabaseXResource, settings: ComposeXSettings
) -> None:
    """
    Function to go over each service defined in the DB and assign found DB settings to service
    """
    for target in db.families_targets:
        add_update_mapping(
            target[0].template,
            db.module.mapping_key,
            settings.mappings[db.module.mapping_key],
        )
        handle_import_dbs_to_services(db, target)


def handle_new_tcp_resource(
    resource: NetworkXResource | DatabaseXResource,
    port_parameter: Parameter,
    sg_parameter: Parameter,
    settings: ComposeXSettings,
    secret_parameter=None,
):
    """
    Funnction to standardize TCP services access from services.

    :param resource:
    :param port_parameter:
    :param sg_parameter:
    :param secret_parameter:
    :return:
    """
    print(
        resource.name,
        resource.stack.title,
        resource.stack.parent_stack.title
        if resource.stack.parent_stack
        else "NO PARENT",
    )
    # if resource.logical_name not in resource.stack.stack_template.resources:
    #     raise KeyError(
    #         f"DB {resource.logical_name} not defined in {resource.stack.title} root template",
    #         list(resource.stack.stack_template.resources.keys()),
    #     )

    for target in resource.families_targets:
        if target[0].service_compute.launch_type == "EXTERNAL":
            LOG.warning(
                f"{resource.stack.title} - {target[0].name} - "
                "When using EXTERNAL Launch Type, networking settings cannot be set."
            )
            continue
        LOG.info(f"{resource.stack.title} - Linking to {target[0].name}")
        if not sg_parameter or not port_parameter:
            LOG.warning(
                f"{resource.module.res_key}.{resource.name}"
                f"Security Group or Port parameter not set. Skipping."
            )
            continue
        sg_id = resource.add_attribute_to_another_stack(
            target[0].stack, sg_parameter, settings
        )
        port_id = resource.add_attribute_to_another_stack(
            target[0].stack, port_parameter, settings
        )

        add_security_group_ingress(
            target[0].stack,
            resource.logical_name,
            sg_id=Ref(sg_id["ImportParameter"]),
            port=Ref(port_id["ImportParameter"]),
        )
        if secret_parameter:
            secret_id = resource.add_attribute_to_another_stack(
                target[0].stack, secret_parameter, settings
            )
            handle_db_secret_to_services(
                resource, Ref(secret_id["ImportParameter"]), target
            )
        else:
            LOG.debug(
                f"No secret_parameter for {resource.module.res_key}.{resource.name}"
            )
        if (
            resource.stack.parent_stack == settings.root_stack
            or not resource.stack.parent_stack
        ) and resource.stack.title not in target[0].stack.DependsOn:
            target[0].stack.DependsOn.append(resource.stack.title)
