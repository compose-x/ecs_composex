#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""Parameters for AWS Managed Prometheus (APS)"""


from ecs_composex.common.troposphere_tools import Parameter

WORKSPACE_GROUP = "Managed Prometheus"

WORKSPACE_ARN = Parameter("Arn", group_label=WORKSPACE_GROUP, Type="String")
WORKSPACE_ID = Parameter(
    "WorkspaceId",
    group_label=WORKSPACE_GROUP,
    return_value="WorkspaceId",
    Type="String",
)
WORKSPACE_ENDPOINT = Parameter(
    "PrometheusEndpoint",
    group_label=WORKSPACE_GROUP,
    return_value="PrometheusEndpoint",
    Type="String",
)
WORKSPACE_REMOTE_WRITE_URL = Parameter(
    "RemoteWriteUrl", group_label=WORKSPACE_GROUP, Type="String"
)

WORKSPACE_QUERY_URL = Parameter("QueryUrl", group_label=WORKSPACE_GROUP, Type="String")

CONTROL_CLOUD_ATTR_MAPPING = {
    WORKSPACE_ARN: "Arn",
    WORKSPACE_ID: "WorkspaceId",
    WORKSPACE_ENDPOINT: "PrometheusEndpoint",
}
