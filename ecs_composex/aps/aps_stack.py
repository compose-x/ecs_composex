# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Manage Creation/Deletion of AWS KMS Keys
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from troposphere import Template
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule

from compose_x_common.aws.aps import APS_WORKSPACE_ARN_RE
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import FindInMap, GetAtt, Ref, Sub, Tags
from troposphere.aps import LoggingConfiguration, Workspace
from troposphere.logs import LogGroup

from ecs_composex.aps.aps_parameters import (
    CONTROL_CLOUD_ATTR_MAPPING,
    WORKSPACE_ARN,
    WORKSPACE_ENDPOINT,
    WORKSPACE_ID,
    WORKSPACE_QUERY_URL,
    WORKSPACE_REMOTE_WRITE_URL,
)
from ecs_composex.common.logging import LOG
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.common.troposphere_tools import (
    Parameter,
    add_outputs,
    add_resource,
    build_template,
)
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.resources_import import import_record_properties


class ManagedPrometheus(ApiXResource):
    """
    Class to represent a KMS Key
    """

    def __init__(
        self,
        name: str,
        definition: dict,
        module: XResourceModule,
        settings: ComposeXSettings,
    ):
        super().__init__(name, definition, module, settings)
        self.cloud_control_attributes_mapping = CONTROL_CLOUD_ATTR_MAPPING
        self.arn_parameter = WORKSPACE_ARN
        self.ref_parameter = WORKSPACE_ARN
        self.support_defaults = True

    def init_outputs(self):
        self.output_properties = {
            WORKSPACE_ARN: (
                f"{self.logical_name}{WORKSPACE_ARN.title}",
                self.cfn_resource,
                Ref,
                None,
            ),
            WORKSPACE_ID: (
                f"{self.logical_name}{WORKSPACE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                WORKSPACE_ID.return_value,
            ),
            WORKSPACE_ENDPOINT: (
                f"{self.logical_name}{WORKSPACE_ENDPOINT.return_value}",
                self.cfn_resource,
                GetAtt,
                WORKSPACE_ENDPOINT.return_value,
            ),
        }

    def add_extra_outputs(self):
        if self.cfn_resource or not self.lookup:
            self.add_new_output_attribute(
                WORKSPACE_QUERY_URL,
                (
                    f"{self.logical_name}{WORKSPACE_QUERY_URL.title}",
                    self.cfn_resource,
                    Sub,
                    f"${{{self.logical_name}.{WORKSPACE_ENDPOINT.return_value}}}api/v1/query",
                ),
                False,
            )
            self.add_new_output_attribute(
                WORKSPACE_REMOTE_WRITE_URL,
                (
                    f"{self.logical_name}{WORKSPACE_REMOTE_WRITE_URL.title}",
                    self.cfn_resource,
                    Sub,
                    f"${{{self.logical_name}.{WORKSPACE_ENDPOINT.return_value}}}api/v1/remote_write",
                ),
                False,
            )
        elif self.lookup_properties:
            self.attributes_outputs[WORKSPACE_REMOTE_WRITE_URL] = {
                "Name": f"{self.logical_name}{WORKSPACE_REMOTE_WRITE_URL.title}",
                "ImportValue": Sub(
                    "${ENDPOINT}api/v1/remote_write",
                    ENDPOINT=self.attributes_outputs[WORKSPACE_ENDPOINT]["ImportValue"],
                ),
                "ImportParameter": Parameter(
                    f"{self.logical_name}{WORKSPACE_REMOTE_WRITE_URL.title}",
                    group_label=WORKSPACE_REMOTE_WRITE_URL.group_label,
                    return_value=WORKSPACE_REMOTE_WRITE_URL.return_value,
                    Type=WORKSPACE_REMOTE_WRITE_URL.Type,
                ),
            }
            self.attributes_outputs[WORKSPACE_QUERY_URL] = {
                "Name": f"{self.logical_name}{WORKSPACE_QUERY_URL.title}",
                "ImportValue": Sub(
                    "${ENDPOINT}api/v1/query",
                    ENDPOINT=self.attributes_outputs[WORKSPACE_ENDPOINT]["ImportValue"],
                ),
                "ImportParameter": Parameter(
                    f"{self.logical_name}{WORKSPACE_QUERY_URL.title}",
                    group_label=WORKSPACE_QUERY_URL.group_label,
                    return_value=WORKSPACE_QUERY_URL.return_value,
                    Type=WORKSPACE_QUERY_URL.Type,
                ),
            }


def create_aps_log_group(
    new_aps: ManagedPrometheus,
    props: dict,
    macro_value: Union[bool, dict],
    template: Template,
) -> None:
    """Handles the CreateNewLogGroup macro parameter"""
    log_group_tags = Tags(ApsWorkspace=new_aps.name)
    if isinstance(macro_value, bool):
        log_group_props = {"Tags": log_group_tags, "RetentionInDays": 7}
    elif isinstance(macro_value, dict):
        log_group_props = import_record_properties(macro_value, LogGroup)
    else:
        raise TypeError(
            f"MacroParameter CreateNewLogGroup is invalid. Got {type(macro_value)} - Expected one of {(bool, dict)}"
        )
    log_group = add_resource(
        template, LogGroup(f"{new_aps.logical_name}LoggingGroup", **log_group_props)
    )
    props.update(
        {
            "LoggingConfiguration": LoggingConfiguration(
                LogGroupArn=GetAtt(log_group, "Arn")
            )
        }
    )


def set_new_aps(
    new_resources: list[ManagedPrometheus], template: Template, stack: ComposeXStack
) -> None:
    """Imports new Managed Prometheus Workspace definition(s) to create new resources"""
    for new_aps in new_resources:
        new_aps.stack = stack
        new_aps_props = import_record_properties(new_aps.properties, Workspace)
        if new_aps.parameters:
            create_log_group = set_else_none("CreateNewLogGroup", new_aps.parameters)
            if create_log_group:
                create_aps_log_group(new_aps, new_aps_props, create_log_group, template)
        new_aps.cfn_resource = add_resource(
            template, Workspace(new_aps.logical_name, **new_aps_props)
        )
        new_aps.init_outputs()
        new_aps.add_extra_outputs()
        new_aps.generate_outputs()
        add_outputs(template, new_aps.outputs)


class XStack(ComposeXStack):
    """
    Class for KMS Root stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.new_resources:
            stack_template = build_template(
                f"APS Template by ECS compose-x for {settings.name}"
            )
            super().__init__(title, stack_template, **kwargs)
            set_new_aps(module.new_resources, stack_template, self)
            if not hasattr(self, "DeletionPolicy"):
                setattr(self, "DeletionPolicy", module.module_deletion_policy)
        else:
            self.is_void = True
        if module.lookup_resources:
            if not keyisset(module.mapping_key, settings.mappings):
                settings.mappings[module.mapping_key] = {}
            for resource in module.lookup_resources:
                resource.lookup_resource(
                    APS_WORKSPACE_ARN_RE,
                    None,
                    Workspace.resource_type,
                    "aps:workspace",
                    use_arn_for_id=True,
                )
                settings.mappings[module.mapping_key].update(
                    {resource.logical_name: resource.mappings}
                )
                resource.add_extra_outputs()
        for resource in module.resources_list:
            resource.stack = self
