#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import json

from compose_x_common.compose_x_common import keyisset
from troposphere.opensearchservice import Domain

from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.opensearch.opensearch_params import (
    OS_DOMAIN_ARN,
    OS_DOMAIN_ARN_RE,
    OS_DOMAIN_ENDPOINT,
    OS_DOMAIN_ID,
    OS_DOMAIN_PORT,
    OS_DOMAIN_SG,
)


def get_domain_config(arn, session):
    """
    Function to retrieve the Domain settings

    :param arn:
    :param session:
    :return:
    """
    client = session.client("cloudcontrol")
    identifier = OS_DOMAIN_ARN_RE.match(arn).group("domain")
    resource = client.get_resource(TypeName=Domain.resource_type, Identifier=identifier)
    if keyisset("ResourceDescription", resource) and keyisset(
        "Properties", resource["ResourceDescription"]
    ):
        props = json.loads(resource["ResourceDescription"]["Properties"])
        mapping = {
            OS_DOMAIN_ARN: props["DomainArn"],
            OS_DOMAIN_ENDPOINT: props["DomainEndpoint"],
            OS_DOMAIN_ID: props["DomainName"],
            OS_DOMAIN_PORT: OS_DOMAIN_PORT.Default,
        }
        if keyisset("VPCOptions", props):
            mapping[OS_DOMAIN_SG] = props["VPCOptions"]["SecurityGroupIds"][0]
        return mapping


def lookup_resource(lookup, session):
    os_types = {"es:domain": {"regexp": OS_DOMAIN_ARN_RE.pattern}}
    lookup_session = define_lookup_role_from_info(lookup, session)

    domain_arn = find_aws_resource_arn_from_tags_api(
        lookup, lookup_session, "es:domain", types=os_types
    )
    return get_domain_config(domain_arn, lookup_session)


def create_opensearch_mappings(lookup_resources, settings):
    """
    Updates the mappings for the Lookup resources

    :param list[ecs_composex.opensearch.opensearch_stack.OpenSearchDomain] lookup_resources:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    """
    for resource in lookup_resources:
        resource.lookup_properties = lookup_resource(resource.lookup, settings.session)
        resource.init_outputs()
        resource.generate_cfn_mappings_from_lookup_properties()
        resource.generate_outputs()
        settings.mappings[resource.module.mapping_key][
            resource.logical_name
        ] = resource.mappings
