# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to handle the AWS ES Stack and resources creation
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from ecs_composex.mods_manager import XResourceModule


import json

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref, Sub
from troposphere.ssm import Parameter as SSMParameter

from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.helpers import (
    set_lookup_resources,
    set_new_resources,
    set_resources,
)
from ecs_composex.compose.x_resources.network_x_resources import NetworkXResource
from ecs_composex.elasticache.elasticache_ecs import create_lookup_mappings
from ecs_composex.elasticache.elasticache_params import (
    CLUSTER_CONFIG,
    CLUSTER_MEMCACHED_ADDRESS,
    CLUSTER_MEMCACHED_PORT,
    CLUSTER_NAME,
    CLUSTER_REDIS_ADDRESS,
    CLUSTER_REDIS_PORT,
    CLUSTER_SG,
    REPLICA_PRIMARY_ADDRESS,
    REPLICA_PRIMARY_PORT,
    REPLICA_READ_ENDPOINT_ADDRESSES,
    REPLICA_READ_ENDPOINT_PORTS,
)
from ecs_composex.elasticache.elasticache_template import create_root_template
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS


class CacheCluster(NetworkXResource):
    """
    Class to represent an AWS Elastic CacheCluster
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        self.db_sg = None
        self.parameter_group = None
        self.db_secret = None
        self.db_subnet_group = None
        self.engine = None
        self.port_attr = None
        self.config_parameter = None
        super().__init__(name, definition, module, settings)
        self.set_override_subnets()

    def init_memcached_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            CLUSTER_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            CLUSTER_MEMCACHED_PORT: (
                f"{self.logical_name}{CLUSTER_MEMCACHED_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_MEMCACHED_PORT.return_value,
            ),
            CLUSTER_MEMCACHED_ADDRESS: (
                f"{self.logical_name}{CLUSTER_MEMCACHED_ADDRESS.return_value}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_MEMCACHED_ADDRESS.return_value,
            ),
            CLUSTER_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                CLUSTER_SG.return_value,
            ),
        }

    def add_memcahed_config(self, template):
        self.port_attr = CLUSTER_MEMCACHED_PORT
        if not self.lookup:
            self.config_parameter = SSMParameter(
                f"{self.logical_name}Config",
                template=template,
                Type="String",
                Value=Sub(
                    json.dumps(
                        {
                            "endpoint": f"${{{self.logical_name}.{CLUSTER_MEMCACHED_ADDRESS.return_value}}}",
                            "port": f"${{{self.logical_name}.{CLUSTER_MEMCACHED_PORT.return_value}}}",
                        }
                    ),
                ),
            )
            self.output_properties[CLUSTER_CONFIG] = (
                self.config_parameter.title,
                self.config_parameter,
                Ref,
                None,
            )

    def init_redis_replica_outputs(self):
        self.output_properties = {
            CLUSTER_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            REPLICA_PRIMARY_PORT: (
                f"{self.logical_name}{REPLICA_PRIMARY_PORT.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_PRIMARY_PORT.return_value,
            ),
            REPLICA_PRIMARY_ADDRESS: (
                f"{self.logical_name}{REPLICA_PRIMARY_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_PRIMARY_ADDRESS.return_value,
            ),
            REPLICA_READ_ENDPOINT_ADDRESSES: (
                f"{self.logical_name}{REPLICA_READ_ENDPOINT_ADDRESSES.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_READ_ENDPOINT_ADDRESSES.return_value,
            ),
            REPLICA_READ_ENDPOINT_PORTS: (
                f"{self.logical_name}{REPLICA_READ_ENDPOINT_PORTS.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_READ_ENDPOINT_PORTS.return_value,
            ),
            CLUSTER_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                CLUSTER_SG.return_value,
            ),
        }
        self.port_attr = REPLICA_PRIMARY_PORT

    def add_redis_replica_config(self, template):
        if not self.lookup:
            self.config_parameter = SSMParameter(
                f"{self.logical_name}Config",
                template=template,
                Type="String",
                Value=Sub(
                    json.dumps(
                        {
                            "endpoint": f"${{{self.logical_name}.{REPLICA_PRIMARY_ADDRESS.return_value}}}",
                            "port": f"${{{self.logical_name}.{REPLICA_PRIMARY_PORT.return_value}}}",
                            "readendpoints": f"{{{self.logical_name}{REPLICA_READ_ENDPOINT_ADDRESSES.return_value}}}",
                            "readports": f"{{{self.logical_name}{REPLICA_READ_ENDPOINT_PORTS.return_value}}}",
                            "url": f"redis://${{{self.logical_name}.{REPLICA_PRIMARY_ADDRESS.return_value}}}:"
                            f"${{{self.logical_name}.{REPLICA_PRIMARY_PORT.return_value}}}",
                        }
                    ),
                ),
            )
            self.output_properties[CLUSTER_CONFIG] = (
                self.config_parameter.title,
                self.config_parameter,
                Ref,
                None,
            )

    def init_redis_outputs(self):
        self.output_properties = {
            CLUSTER_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            CLUSTER_REDIS_PORT: (
                f"{self.logical_name}{CLUSTER_REDIS_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_REDIS_PORT.return_value,
            ),
            CLUSTER_REDIS_ADDRESS: (
                f"{self.logical_name}{CLUSTER_REDIS_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_REDIS_ADDRESS.return_value,
            ),
            CLUSTER_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                CLUSTER_SG.return_value,
            ),
        }
        self.port_attr = CLUSTER_REDIS_PORT

    def add_redis_config(self, template):
        if not self.lookup:
            self.config_parameter = SSMParameter(
                f"{self.logical_name}Config",
                template=template,
                Type="String",
                Value=Sub(
                    json.dumps(
                        {
                            "endpoint": f"${{{self.logical_name}.{CLUSTER_REDIS_ADDRESS.return_value}}}",
                            "port": f"${{{self.logical_name}.{CLUSTER_REDIS_PORT.return_value}}}",
                            "url": f"redis://${{{self.logical_name}.{CLUSTER_REDIS_ADDRESS.return_value}}}:"
                            f"${{{self.logical_name}.{CLUSTER_REDIS_PORT.return_value}}}",
                        }
                    ),
                ),
            )
            self.output_properties[CLUSTER_CONFIG] = (
                self.config_parameter.title,
                self.config_parameter,
                Ref,
                None,
            )


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(
        self, title, settings: ComposeXSettings, module: XResourceModule, **kwargs
    ):
        if module.lookup_resources:
            if not keyisset(module.res_key, settings.mappings):
                settings.mappings[module.res_key] = {}
            create_lookup_mappings(
                settings.mappings[module.res_key], module.lookup_resources, settings
            )

        if module.new_resources:
            stack_template = create_root_template(module.new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True

        for resource in module.resources_list:
            resource.stack = self
