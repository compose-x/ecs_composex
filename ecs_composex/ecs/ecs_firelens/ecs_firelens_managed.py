#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handles ``Rendered`` section of the FireLens configuration
"""
import copy
from os import environ, path
from tempfile import TemporaryDirectory

from compose_x_common.compose_x_common import keyisset, keypresent, set_else_none
from jinja2 import Environment, FileSystemLoader

from ecs_composex.common import LOG


class FireLensManagedConfiguration:
    compose_files_image: str = "public.ecr.aws/compose-x/ecs-files-composer:v0.7.3"

    def __init__(self, definition):
        self._definition = copy.deepcopy(definition)
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
    def managed_firehose_destinations(self):
        managed_firehose: list = []
        for _managed_dest in self.managed_destinations:
            if isinstance(_managed_dest, FireLensFirehoseManagedDestination):
                managed_firehose.append(_managed_dest)
        return managed_firehose

    @property
    def healtchek_enabled(self) -> bool:
        enable_health_check = (
            True
            if not keypresent("EnableHeathCheck", self.definition)
            else keyisset("EnableHeathCheck", self.definition)
        )
        return enable_health_check

    @property
    def grace_period(self) -> int:
        return set_else_none("GracePeriod", self.definition, alt_value=30)

    @property
    def source_file_content(self) -> str:
        if not self.source_file:
            return ""
        with open(path.abspath(self.source_file)) as config_fd:
            return config_fd.read()

    def render_jinja_config_file(self):
        here = path.abspath(path.dirname(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(here),
            autoescape=True,
            auto_reload=False,
        )
        template = jinja_env.get_template("fluentbit_managed_config.j2")
        content = template.render(
            env=environ,
            enable_health_check=self.healtchek_enabled,
            grace_period=self.grace_period,
            firelens_firehose_destinations=self.managed_firehose_destinations,
            source_file=self.source_file_content,
        )
        print(content)
        return content


class FireLensCloudWatchManagedDestination:
    def __init__(self, definition: dict):
        self._definition = definition
        self.output_definition = None

    @property
    def log_group_name(self) -> str:
        return self._definition["log_group_name"]


class FireLensFirehoseManagedDestination:
    required = [
        "delivery_stream",
        "region",
    ]
    options = [
        "role_arn",
        "time_key_format",
        "time_key",
        "log_key",
        "compression",
        "endpiont",
        "sts_endpoint",
        "auto_retry_requests",
    ]

    def __init__(self, definition: dict):
        self._definition = definition
        self._managed_firehose = None

    @property
    def delivery_stream(self) -> str:
        return self._definition["delivery_stream"]

    @property
    def delivery_stream_fluent_name(self):
        return self._managed_firehose

    @property
    def region(self) -> str:
        if keyisset("region", self._definition):
            return self._definition["region"]
        else:
            return r"${AWS_DEFAULT_REGION}"

    @property
    def is_cross_account(self) -> bool:
        if keyisset("role_arn", self._definition):
            return True
        return False

    @property
    def output_definition(self):
        config: dict = {
            "region": self.region,
            "delivery_stream": self.delivery_stream_fluent_name,
        }
        for option_name in self.options:
            if keyisset(option_name, self._definition):
                config.update({option_name: self._definition[option_name]})
        return config
