#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


"""
OpenSearch module to manage creation of new OpenSearch domains
"""
import json
import re

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_NO_VALUE,
    AWS_PARTITION,
    AWS_REGION,
    AWS_URL_SUFFIX,
    GetAtt,
    Ref,
    Sub,
    Tags,
    opensearchservice,
)
from troposphere.ec2 import SecurityGroup
from troposphere.iam import Role
from troposphere.logs import LogGroup, ResourcePolicy

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_conditions import define_stack_name
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_outputs, add_parameters
from ecs_composex.compose.compose_services.service_logging.helpers import (
    get_closest_valid_log_retention_period,
)
from ecs_composex.iam import define_iam_policy
from ecs_composex.opensearch.opensearch_params import OS_DOMAIN_PORT, OS_DOMAIN_SG
from ecs_composex.resources_import import import_record_properties
from ecs_composex.secrets import add_db_secret
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS, VPC_ID


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


def create_log_groups(domain, stack, props):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param dict props:
    :return:
    """
    opts = {}
    all_opts = [
        "SEARCH_SLOW_LOGS",
        "ES_APPLICATION_LOGS",
        "INDEX_SLOW_LOGS",
        "AUDIT_LOGS",
    ]
    opts_to_add = (
        domain.parameters["CreateLogGroups"]
        if isinstance(domain.parameters["CreateLogGroups"], list)
        else all_opts
    )
    groups = []
    for option in opts_to_add:
        group_name = Sub(
            f"opensearch/${{STACK_NAME}}/{domain.logical_name}/{option}",
            STACK_NAME=define_stack_name(stack.stack_template),
        )
        log_group = LogGroup(
            f"{domain.logical_name}{NONALPHANUM.sub('', option)}LogGroup",
            LogGroupName=group_name,
            RetentionInDays=30
            if not keyisset("RetentionInDays", domain.parameters)
            else get_closest_valid_log_retention_period(
                domain.parameters["RetentionInDays"]
            ),
        )
        stack.stack_template.add_resource(log_group)
        groups.append(log_group)
        opts[option] = {
            "Enabled": True,
            "CloudWatchLogsLogGroupArn": Sub(
                f"arn:${{{AWS_PARTITION}}}:logs:${{{AWS_REGION}}}:${{{AWS_ACCOUNT_ID}}}:"
                f"log-group:${{{log_group.title}}}"
            ),
        }
    if keyisset("CreateLogGroupsResourcePolicy", domain.parameters):
        logs_policy = ResourcePolicy(
            "OpenSearchLogGroupResourcePolicy",
            DeletionPolicy="Retain",
            PolicyName="ComposeXOpenSearchAccessToCWLogs",
            PolicyDocument=Sub(
                json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowESDomainsToAccessLogGroupsInAllRegions",
                                "Effect": "Allow",
                                "Principal": {"Service": f"es.${{{AWS_URL_SUFFIX}}}"},
                                "Action": ["logs:PutLogEvents", "logs:CreateLogStream"],
                                "Resource": [
                                    f"arn:${{{AWS_PARTITION}}}:logs:*:${{{AWS_ACCOUNT_ID}}}:log-group:opensearch/*"
                                ],
                            }
                        ],
                    }
                )
            ),
        )
        stack.stack_template.add_resource(logs_policy)
    props["LogPublishingOptions"] = opts


def correcting_required_settings(domain, props):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict props:
    :return:
    """
    if not keyisset("NodeToNodeEncryptionOptions", props):
        props[
            "NodeToNodeEncryptionOptions"
        ] = opensearchservice.NodeToNodeEncryptionOptions(Enabled=True)
    elif (
        keypresent("NodeToNodeEncryptionOptions", domain.parameters)
        and not domain.parameters["NodeToNodeEncryptionOptions"]
    ):
        LOG.warn(
            "You have Advanced Security options enabled but NodeToNodeEncryptionOptions is disabled. Enabling"
        )
        props[
            "NodeToNodeEncryptionOptions"
        ] = opensearchservice.NodeToNodeEncryptionOptions(Enabled=True)

    if keyisset("EncryptionAtRestOptions", props):
        crypt_options = props["EncryptionAtRestOptions"]
        if hasattr(crypt_options, "Enabled") and crypt_options.Enabled is False:
            LOG.warn(
                f"{domain.name} - With Advanced Security options, Encryption at rest must be enabled. Enabling"
            )
            setattr(crypt_options, "Enabled", True)
    else:
        props["EncryptionAtRestOptions"] = opensearchservice.EncryptionAtRestOptions(
            Enabled=True
        )

    if keyisset("DomainEndpointOptions", props):
        settings = props["DomainEndpointOptions"]
        setattr(settings, "EnforceHTTPS", True)
    else:
        props["DomainEndpointOptions"] = opensearchservice.DomainEndpointOptions(
            EnforceHTTPS=True,
        )


def generate_master_user(domain, stack, props):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param dict props:
    :return:
    """
    master_user_opts = {}
    iam_role = None
    if keyisset("GenerateMasterUserSecret", domain.parameters):
        domain.db_secret = add_db_secret(stack.stack_template, domain.logical_name)
        master_user_opts["MasterUserName"] = Sub(
            f"{{{{resolve:secretsmanager:${{{domain.db_secret.title}}}:SecretString:username}}}}"
        )
        master_user_opts["MasterUserPassword"] = Sub(
            f"{{{{resolve:secretsmanager:${{{domain.db_secret.title}}}:SecretString:password}}}}"
        )
        LOG.info(f"{domain.name} - Created Secret for MasterUser")
    if keyisset("CreateMasterUserRole", domain.parameters):
        LOG.info(f"{domain.name} - adding MasterUserARN")
        statement = {
            "Effect": "Allow",
            "Principal": {
                "AWS": [
                    Sub(f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:root")
                ]
            },
            "Action": ["sts:AssumeRole"],
            "Condition": {"Bool": {"aws:SecureTransport": "true"}},
        }
        policy_doc = {"Version": "2012-10-17", "Statement": [statement]}
        iam_role = Role(
            f"{domain.logical_name}MasterUserRole",
            PermissionsBoundary=define_iam_policy(
                domain.parameters["MasterUserRolePermissionsBoundary"]
            )
            if keyisset("MasterUserRolePermissionsBoundary", domain.parameters)
            else Ref(AWS_NO_VALUE),
            AssumeRolePolicyDocument=policy_doc,
        )
        stack.stack_template.add_resource(iam_role)
        master_user_opts["MasterUserARN"] = GetAtt(iam_role, "Arn")
    if not master_user_opts:
        return

    if not keyisset("AdvancedSecurityOptions", props):
        security_opts = opensearchservice.AdvancedSecurityOptionsInput(
            Enabled=True,
            InternalUserDatabaseEnabled=False if not domain.db_secret else True,
            MasterUserOptions=opensearchservice.MasterUserOptions(**master_user_opts),
        )
        props["AdvancedSecurityOptions"] = security_opts
    else:
        LOG.warn(
            f"{domain.name}.Properties.AdvancedSecurityOptions is set as well as MacroParameters. Overriding"
        )
        security_opts = props["AdvancedSecurityOptions"]
        if security_opts.InternalUserDatabaseEnabled is True and iam_role:
            LOG.warn(
                f"{domain.name} - When using CreateMasterUserRole, you cannot use the Internal DB"
            )
            setattr(security_opts, "InternalUserDatabaseEnabled", False)
        elif security_opts.InternalUserDatabaseEnabled is False and domain.db_secret:
            LOG.warn(
                f"{domain.name} - When using CreateMasterUserRole, you must use the Internal DB"
            )
            setattr(security_opts, "InternalUserDatabaseEnabled", True)
        setattr(
            security_opts,
            "MasterUserOptions",
            opensearchservice.MasterUserOptions(**master_user_opts),
        )
        setattr(security_opts, "Enabled", True)


def apply_domain_parameters(domain, stack, props):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param ecs_composex.common.stacks.ComposeXStack stack:
    :param dict props:
    """
    if keyisset("CreateLogGroups", domain.parameters):
        create_log_groups(domain, stack, props)

    if keyisset("CreateMasterUserRole", domain.parameters) and keyisset(
        "GenerateMasterUserSecret", domain.parameters
    ):
        raise ValueError(
            "You cannot have both a MasterRole and MasterUser at the same time."
        )
    if keyisset("CreateMasterUserRole", domain.parameters) or keyisset(
        "GenerateMasterUserSecret", domain.parameters
    ):
        if (
            keyisset("AdvancedSecurityOptions", props)
            and props["AdvancedSecurityOptions"].InternalUserDatabaseEnabled is True
        ):
            LOG.error(
                f"{domain.name} - You have defined InternalUserDatabaseEnabled to True. MasterUser cannot be used"
            )
        else:
            generate_master_user(domain, stack, props)


def validate_instance_types_config(domain, props, instance_type, config):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict props:
    :param str instance_type:
    :param dict config:
    :raises: ValueError if features are not compatible withe the instance type
    """
    must_be_null = ["EBSOptions"]
    if keyisset("not_supported", config):
        unsupported = config["not_supported"]
        for top_config, false_prop in unsupported.items():
            if keyisset(top_config, props) and hasattr(props[top_config], false_prop):
                value = getattr(props[top_config], false_prop)
                if value is not False:
                    raise ValueError(
                        f"{domain.name} - Property {top_config}.{false_prop} is enabled, but is "
                        f"incompatible with {instance_type} instances type"
                    )
                elif value is False and top_config in must_be_null:
                    LOG.warn(
                        f"{domain.name} - {top_config}.{false_prop} is False but the property must be null. "
                        "Overriding to AWS::NoValue"
                    )
                    props[top_config] = Ref(AWS_NO_VALUE)
    if keyisset("must_have", config):
        must_have = config["must_have"]
        for top_config, req_prop in must_have.items():
            if keyisset(top_config, props) and hasattr(props[top_config], req_prop):
                value = getattr(props[top_config], req_prop)
                if value is not True:
                    raise ValueError(
                        f"{domain.name} - {instance_type} requires {top_config}.{req_prop} to be True"
                    )


def validate_version_support(domain, props, instance_type, config):
    """

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict props:
    :param str instance_type:
    :param dict config:
    :raises: ValueError if features are not compatible withe the instance type
    """
    if not keyisset("EngineVersion", props):
        return
    if not keyisset("EngineVersion", config):
        return
    engine_version = props["EngineVersion"]
    engine_support = config["EngineVersion"]
    version_re = re.compile(
        r"(?P<engine>OpenSearch|Elasticsearch)_(?P<version>\d+.\d+)$"
    )
    if not version_re.match(engine_version):
        raise ValueError(
            f"{domain.name} - EngineVersion {engine_version} is not valid. Must match",
            version_re.pattern,
        )
    version_number = float(version_re.match(engine_version).group("version"))
    engine_name = version_re.match(engine_version).group("engine")
    if not keyisset(engine_name, engine_support):
        return
    supported_version = float(engine_support[engine_name])
    if version_number < supported_version:
        raise ValueError(
            f"{domain.name} - EngineVersion {engine_version} is not supported. "
            f"{instance_type} Requires >={engine_name}_{supported_version}"
        )


def validate_no_architecture_mix(domain, types):
    """
    Function to ensure there is no Graviton instances mixed with non-graviton ones

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param list[str] types:
    :raises: ValueError if not all instances are of the same architecture
    """
    graviton_re = re.compile(r"[a-z]\d(g$|gd$)")
    types_are_graviton = [bool(graviton_re.match(i_type)) for i_type in types]
    if not all(x == types_are_graviton[0] for x in types_are_graviton):
        raise ValueError(
            f"{domain.name} - Not all instances are of the same architecture", types
        )


def correct_properties(domain, props):
    """
    Function to rectify settings in case invalid options were set with each other.

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict props:
    """
    if (
        keyisset("EBSOptions", props)
        and hasattr(props["EBSOptions"], "EBSEnabled")
        and props["EBSOptions"].EBSEnabled is False
    ):
        props["EBSOptions"] = Ref(AWS_NO_VALUE)


def validate_instance_types(domain, props):
    """
    Validates that the settings set are compatible with one another

    :param ecs_composex.opensearch.opensearch_stack.OpenSearchDomain domain:
    :param dict props:
    """
    instance_types = {
        "c4": {},
        "c5": {"EngineVersion": {"Elasticsearch": 5.1, "OpenSearch": 1.0}},
        "c6g": {
            "EngineVersion": {"Elasticsearch": 7.9, "OpenSearch": 1.0},
            "must_have": {"EBSOptions": "EBSEnabled"},
        },
        "i2": {},
        "i3": {
            "EngineVersion": {
                "Elasticsearch": 5.1,
                "OpenSearch": 1.0,
            },
            "not_supported": {"EBSOptions": "EBSEnabled"},
        },
        "m3": {
            "EngineVersion": {"Elasticsearch": 6.5, "OpenSearch": 1.0},
            "not_supported": {
                "EncryptionAtRestOptions": "Enabled",
                "AdvancedSecurityOptions": "Enabled",
            },
        },
        "m4": {},
        "m5": {"EngineVersion": {"Elasticsearch": 5.1, "OpenSearch": 1.0}},
        "m6g": {
            "EngineVersion": {
                "Elasticsearch": 7.9,
                "OpenSearch": 1.0,
            },
            "must_have": {"EBSOptions": "EBSEnabled"},
        },
        "r3": {
            "EngineVersion": {"OpenSearch": 1.0, "Elasticsearch": 6.5},
            "not_supported": {
                "EncryptionAtRestOptions": "Enabled",
                "AdvancedSecurityOptions": "Enabled",
            },
        },
        "r4": {},
        "r5": {"EngineVersion": {"OpenSearch": 1.0, "Elasticsearch": 5.1}},
        "r6g": {
            "EngineVersion": {
                "OpenSearch": 1.0,
                "Elasticsearch": 7.9,
            },
            "must_have": {"EBSOptions": "EBSEnabled"},
        },
        "r6gd": {
            "EngineVersion": {"OpenSearch": 1.0, "Elasticsearch": 7.9},
            "not_supported": {"EBSOptions": "EBSEnabled"},
        },
        "t2": {
            "EngineVersion": {"OpenSearch": 1.0, "Elasticsearch": 6.5},
            "not_supported": {
                "EncryptionAtRestOptions": "Enabled",
                "AdvancedSecurityOptions": "Enabled",
                "ClusterConfig": "WarmEnabled",
            },
        },
        "t3": {
            "EngineVersion": {"OpenSearch": 1.0, "Elasticsearch": 6.5},
            "not_supported": {
                "EncryptionAtRestOptions": "Enabled",
                "AdvancedSecurityOptions": "Enabled",
                "ClusterConfig": "WarmEnabled",
            },
        },
    }
    if not keyisset("ClusterConfig", props):
        return
    instance_types_logged = []
    cluster_type_props = ["DedicatedMasterType", "InstanceType", "WarmType"]
    cluster_config = props["ClusterConfig"]
    for cluster_type_prop in cluster_type_props:
        if not hasattr(cluster_config, cluster_type_prop):
            continue
        defined_type = getattr(cluster_config, cluster_type_prop).split(".")[0]
        if defined_type not in instance_types.keys():
            raise ValueError(
                f"{domain.name} - Instance Type for {cluster_type_prop} is not valid",
                getattr(cluster_config, cluster_type_prop),
                list(instance_types.keys()),
            )
        instance_types_logged.append(defined_type)
        config = instance_types[defined_type]
        validate_version_support(domain, props, defined_type, config)
        validate_instance_types_config(domain, props, defined_type, config)
    validate_no_architecture_mix(domain, instance_types_logged)
    correct_properties(domain, props)


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
        if domain.parameters:
            apply_domain_parameters(domain, stack, props)
        if keyisset("AdvancedSecurityOptions", props):
            correcting_required_settings(domain, props)
        validate_instance_types(domain, props)
        domain.cfn_resource = opensearchservice.Domain(domain.logical_name, **props)
        domain.init_outputs()
        stack.stack_template.add_resource(domain.cfn_resource)
        domain.generate_outputs()
        if domain.security_group:
            domain.add_new_output_attribute(
                OS_DOMAIN_SG,
                (
                    f"{domain.logical_name}{OS_DOMAIN_SG.return_value}",
                    domain.security_group,
                    GetAtt,
                    OS_DOMAIN_SG.return_value,
                ),
            )
            domain.add_new_output_attribute(
                OS_DOMAIN_PORT,
                (
                    f"{domain.logical_name}{OS_DOMAIN_PORT.title}",
                    OS_DOMAIN_PORT.Default,
                    OS_DOMAIN_PORT.Default,
                    False,
                ),
            )
            add_parameters(stack.stack_template, [OS_DOMAIN_PORT])
        add_outputs(stack.stack_template, domain.outputs)
