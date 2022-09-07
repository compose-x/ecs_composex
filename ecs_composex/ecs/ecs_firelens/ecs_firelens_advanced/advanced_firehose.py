#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings
    from . import FireLensServiceManagedConfiguration

from compose_x_common.aws.arns import KINESIS_FIREHOSE_ARN_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import Region

from ecs_composex.ecs.ecs_firelens.firelens_options_generic_helpers import (
    handle_cross_account_permissions,
)
from ecs_composex.ecs.ecs_firelens.helpers.firehose_helpers import (
    add_firehose_delivery_stream_for_firelens,
)
from ecs_composex.kinesis_firehose.kinesis_firehose_params import FIREHOSE_ARN
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream


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
        "endpoint",
        "sts_endpoint",
        "auto_retry_requests",
    ]

    def __init__(
        self,
        definition: dict,
        advanced_config: FireLensServiceManagedConfiguration,
        settings: ComposeXSettings,
    ):
        self._definition = definition
        self.parent = advanced_config
        if self._definition["delivery_stream"].startswith("x-kinesis_firehose"):
            self._managed_firehose = settings.find_resource(
                self._definition["delivery_stream"]
            )
            add_firehose_delivery_stream_for_firelens(
                self._managed_firehose,
                self.parent.extra_env_vars,
                self.parent.family,
                settings,
            )
        else:
            self._managed_firehose = None
            self.parent.extra_env_vars.update(
                {self.delivery_stream_fluent_name: self._definition["delivery_stream"]}
            )
        self.process_all_options(self.parent.family, self.parent.service, settings)

    def process_all_options(self, family, service, settings: ComposeXSettings):
        param_to_handler = {
            "role_arn": handle_cross_account_permissions,
        }
        for param_name, param_function in param_to_handler.items():
            if (
                param_name in self._definition.keys()
                and param_function
                and callable(param_function)
            ):
                service.logging.log_options[param_name] = param_function(
                    family,
                    service,
                    settings,
                    param_name,
                    self._definition[param_name],
                )

    @property
    def delivery_stream(self) -> str:
        if isinstance(self._managed_firehose, DeliveryStream):
            return self._managed_firehose.name
        else:
            return self._definition["delivery_stream"]

    @property
    def delivery_stream_fluent_name(self):
        return rf"${{{self._managed_firehose.env_var_prefix}}}"

    @property
    def region(self) -> str:
        if self._managed_firehose:
            env_var_key = f"{self._managed_firehose.env_var_prefix}_AWS_REGION"
            if self._managed_firehose.cfn_resource:
                self.parent.extra_env_vars.update({env_var_key: Region})
                return rf"${{{env_var_key}}}"
            elif self._managed_firehose.mappings:
                arn_value = self._managed_firehose.mappings[FIREHOSE_ARN.title]
                return KINESIS_FIREHOSE_ARN_RE.match(arn_value).group("region")
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
