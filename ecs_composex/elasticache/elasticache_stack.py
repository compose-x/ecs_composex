﻿#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Module to handle the AWS ES Stack and resources creation
"""

from troposphere import Ref, GetAtt

from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack

from ecs_composex.elasticache.elasticache_params import (
    RES_KEY,
    CLUSTER_NAME,
    CLUSTER_SG,
    CLUSTER_REDIS_PORT,
    CLUSTER_REDIS_ADDRESS,
    CLUSTER_CONFIG_ADDRESS,
    CLUSTER_CONFIG_PORT,
    REPLICA_READ_ENDPOINT_ADDRESSES,
    REPLICA_READ_ENDPOINT_PORTS,
    REPLICA_PRIMARY_ADDRESS,
    REPLICA_PRIMARY_PORT,
)
from ecs_composex.elasticache.elasticache_template import create_root_template


class CacheCluster(XResource):
    """
    Class to represent an AWS Elastic CacheCluster
    """

    def __init__(self, name, definition, settings):
        self.db_sg = None
        self.parameter_group = None
        self.db_secret = None
        self.engine = None
        self.port_attr = None
        super().__init__(name, definition, settings)

    def init_memcached_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            CLUSTER_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            CLUSTER_CONFIG_PORT.title: (
                f"{self.logical_name}{CLUSTER_CONFIG_PORT.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_CONFIG_PORT.Description,
            ),
            CLUSTER_CONFIG_ADDRESS.title: (
                f"{self.logical_name}{CLUSTER_CONFIG_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_CONFIG_ADDRESS.Description,
            ),
            self.db_sg.title: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                "GroupId",
            ),
        }
        self.port_attr = CLUSTER_CONFIG_PORT

    def init_redis_replica_outputs(self):
        self.output_properties = {
            CLUSTER_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            REPLICA_PRIMARY_PORT.title: (
                f"{self.logical_name}{REPLICA_PRIMARY_PORT.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_PRIMARY_PORT.Description,
            ),
            REPLICA_PRIMARY_ADDRESS.title: (
                f"{self.logical_name}{REPLICA_PRIMARY_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_PRIMARY_ADDRESS.Description,
            ),
            REPLICA_READ_ENDPOINT_ADDRESSES.title: (
                f"{self.logical_name}{REPLICA_READ_ENDPOINT_ADDRESSES.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_READ_ENDPOINT_ADDRESSES.Description,
            ),
            REPLICA_READ_ENDPOINT_PORTS.title: (
                f"{self.logical_name}{REPLICA_READ_ENDPOINT_PORTS.title}",
                self.cfn_resource,
                GetAtt,
                REPLICA_READ_ENDPOINT_PORTS.Description,
            ),
            self.db_sg.title: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                "GroupId",
            ),
        }
        self.port_attr = REPLICA_PRIMARY_PORT

    def init_redis_outputs(self):
        self.output_properties = {
            CLUSTER_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            CLUSTER_REDIS_PORT.title: (
                f"{self.logical_name}{CLUSTER_REDIS_PORT.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_REDIS_PORT.Description,
            ),
            CLUSTER_REDIS_ADDRESS.title: (
                f"{self.logical_name}{CLUSTER_REDIS_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_REDIS_ADDRESS.Description,
            ),
            self.db_sg.title: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                "GroupId",
            ),
        }
        self.port_attr = CLUSTER_REDIS_PORT


class XStack(ComposeXStack):
    """
    Method to manage the elastic cache resources and root stack
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, CacheCluster, RES_KEY)
        new_resources = [
            settings.compose_content[RES_KEY][res_name]
            for res_name in settings.compose_content[RES_KEY]
            if not settings.compose_content[RES_KEY][res_name].lookup
        ]
        if new_resources:
            stack_template = create_root_template(new_resources)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
