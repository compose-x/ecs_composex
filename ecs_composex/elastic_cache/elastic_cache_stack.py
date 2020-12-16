#  -*- coding: utf-8 -*-
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

from ecs_composex.elastic_cache.elastic_cache_params import (
    RES_KEY,
    CLUSTER_NAME,
    CLUSTER_SG,
    CLUSTER_PORT,
    CLUSTER_ADDRESS,
    CLUSTER_CONFIG_ADDRESS,
    CLUSTER_CONFIG_PORT,
)
from ecs_composex.elastic_cache.elastic_cache_template import create_root_template


class CacheCluster(XResource):
    """
    Class to represent an AWS Elastic CacheCluster
    """

    def __init__(self, name, definition, settings):
        self.cluster_sg = None
        self.parameter_group = None
        super().__init__(name, definition, settings)

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            CLUSTER_NAME.title: (self.logical_name, self.cfn_resource, Ref, None),
            CLUSTER_PORT.title: (
                f"{self.logical_name}{CLUSTER_PORT.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_PORT.Description,
            ),
            CLUSTER_ADDRESS.title: (
                f"{self.logical_name}{CLUSTER_ADDRESS.title}",
                self.cfn_resource,
                GetAtt,
                CLUSTER_PORT.Description,
            ),
            self.cluster_sg.title: (
                self.cluster_sg.title,
                self.cluster_sg,
                GetAtt,
                "GroupId",
            ),
        }


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
            stack_template = create_root_template(new_resources, settings)
            super().__init__(title, stack_template, **kwargs)
        else:
            self.is_void = True
