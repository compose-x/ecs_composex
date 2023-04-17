# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>


from ecs_composex.common.cfn_params import Parameter

GROUPS_LABEL = "WAFv2 WebACL"

WEB_ACL_REF_T = "Ref"
WEB_ACL_REF = Parameter(WEB_ACL_REF_T, group_label=GROUPS_LABEL, Type="String")

WEB_ACL_ARN_T: str = "Arn"
WEB_ACL_ARN = Parameter(
    WEB_ACL_ARN_T, group_label=GROUPS_LABEL, return_value="Arn", Type="String"
)

WEB_ACL_WCU_T = "Capacity"
WEB_ACL_WCU = Parameter(
    WEB_ACL_WCU_T, group_label=GROUPS_LABEL, return_value="Capacity", Type="Number"
)

WEB_ACL_ID_T = "Id"
WEB_ACL_ID = Parameter(
    WEB_ACL_ID_T, group_label=GROUPS_LABEL, return_value="Id", Type="String"
)

WEB_ACL_NAMESPACE_T: str = "LabelNamespace"
WEB_ACL_NAMESPACE = Parameter(
    WEB_ACL_NAMESPACE_T,
    group_label=GROUPS_LABEL,
    return_value="LabelNamespace",
    Type="String",
)

CONTROL_CLOUD_ATTR_MAPPING = {
    WEB_ACL_ARN: WEB_ACL_ARN.return_value,
    WEB_ACL_ID: WEB_ACL_ID.return_value,
    # WEB_ACL_WCU: WEB_ACL_WCU.return_value,
    WEB_ACL_NAMESPACE: WEB_ACL_NAMESPACE.return_value,
}
