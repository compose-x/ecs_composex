#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handles ``Rendered`` section of the FireLens configuration
"""
import copy
from os import path

from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common import LOG


class FireLensManagedConfiguration:

    compose_files_image: str = "public.ecr.aws/compose-x/ecs-files-composer:v0.7.3"

    def __init__(self, definition):
        self._definition = copy.deepcopy(definition)
        self.auto_cloudwatch = keyisset("AutoCloudWatch", self.definition)
        self.source_file = set_else_none("SourceFile", self.definition)
        self._env_vars = set_else_none("EnvironmentVariables", self.definition)
        self.ssm_parameter = None
        self.managed_destinations = []
        if keyisset("ComposeXManagedAwsDestinations", self.definition):
            for destination_definition in self.definition[
                "ComposeXManagedAwsDestinations"
            ]:
                if keyisset("log_group_name", destination_definition):
                    self.managed_destinations.append(
                        FireLensCloudWatchManagedDestination(destination_definition)
                    )
                elif keyisset("delivery_stream", destination_definition):
                    self.managed_destinations.append(
                        FireLensFirehoseManagedDestination(destination_definition)
                    )
                else:
                    LOG.error("Invalid definition for ComposeXManagedAwsDestinations")
                    LOG.error(destination_definition)

    @property
    def definition(self):
        return self._definition

    @property
    def source_file_content(self) -> str:
        with open(path.abspath(self.source_file)) as config_fd:
            return config_fd.read()


class FireLensCloudWatchManagedDestination:
    def __init__(self, definition: dict):
        self._definition = definition
        self.output_definition = None

    @property
    def log_group_name(self) -> str:
        return self._definition["log_group_name"]


class FireLensFirehoseManagedDestination:
    def __init__(self, definition: dict):
        self._definition = definition
        self.output_definition = None

    @property
    def delivery_stream(self) -> str:
        return self._definition["delivery_stream"]

    @property
    def is_cross_account(self) -> bool:
        if keyisset("role_arn", self._definition):
            return True
        return False
