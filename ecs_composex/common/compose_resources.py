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
Module to define the ComposeX Resources into a simple object to make it easier to navigate through.
"""

from troposphere import Sub

from ecs_composex.common.cfn_params import ROOT_STACK_NAME
from ecs_composex.common import NONALPHANUM, keyisset


def set_resources(settings, resource_class, res_key):
    """
    Method to define the ComposeXResource for each service.

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :param resource_class:
    :param str res_key:
    """
    for resource_name in settings.compose_content[res_key]:
        settings.compose_content[res_key][resource_name] = resource_class(
            resource_name, settings.compose_content[res_key][resource_name]
        )


class Service(object):
    """
    Class to represent a service

    :cvar str container_name: name of the container to use in definitions
    """

    def __init__(self, name, definition):
        self.name = name
        self.definition = definition
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.container_name = name
        self.service_name = Sub(f"${{{ROOT_STACK_NAME.title}}}-{self.name}")
        self.cfn_resource = None


class XResource(object):
    """
    Class to represent each defined resource in the template

    :cvar str name: The name of the resource as defined in compose file
    :cvar dict definition: The definition of the resource as defined in compose file
    :cvar str logical_name: Name of the resource to use in CFN template as for export/import
    """

    def __init__(self, name, definition):
        """
        Init the class
        :param str name: Name of the resource in the template
        :param str resource_type: The category of resource.
        :param dict definition: The definition of the resource as-is
        """
        self.name = name
        self.definition = definition
        self.logical_name = NONALPHANUM.sub("", self.name)
        self.settings = (
            None
            if not keyisset("Settings", self.definition)
            else self.definition["Settings"]
        )
        self.properties = (
            None
            if not keyisset("Properties", self.definition)
            else self.definition["Properties"]
        )
        self.services = (
            []
            if not keyisset("Services", self.definition)
            else self.definition["Services"]
        )
        self.lookup = (
            None
            if not keyisset("Lookup", self.definition)
            else self.definition["Lookup"]
        )
        self.use = (
            None if not keyisset("Use", self.definition) else self.definition["Use"]
        )
        self.cfn_resource = None

    def __repr__(self):
        return self.logical_name


class Queue(XResource):
    """
    Class to represent a SQS Queue
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)


class Rds(XResource):
    """
    Class to represent a RDS DB
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)


class Kms(XResource):
    """
    Class to represent a KMS Key
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)


class Table(XResource):
    """
    Class to represent a DynamoDB Table
    """

    def __init__(self, name, definition):
        super().__init__(name, definition)
