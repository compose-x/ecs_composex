#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG


class ComposeXConfig(object):
    """
    Class to parse and define configuration settings for ECS ComposeX
    """

    master_key = "x-configs"
    composex_key = "composex"

    def __init__(self, settings):
        """
        Initializes the ComposeXConfig class

        :param ComposeXSettings settings: The execution settings
        """
        self.composex_config = {}
        if keyisset(self.master_key, settings.compose_content) and keyisset(
            self.composex_key, settings.compose_content[self.master_key]
        ):
            self.composex_config = settings.compose_content[self.master_key][
                self.composex_key
            ]


class ComputeConfig(ComposeXConfig):
    """
    Class to determine the compute settings to use when deploying on top of EC2.
    """

    default_spot_config = {
        "use_spot": True,
        "bid_price": 0.42,
        "spot_instance_types": {
            "m5a.xlarge": {"weight": 3},
            "m5a.2xlarge": {"weight": 7},
            "m5a.4xlarge": {"weight": 15},
        },
    }
    spot_key = "spot_config"

    def __init__(self, settings):
        """
        Method to initialize Compute config

        :param ecs_composex.common.settings.ComposeXSettings settings: The settings for execution
        """
        super().__init__(settings)
        if keyisset(self.spot_key, self.composex_config):
            self.spot_config = self.composex_config[self.spot_key]
        else:
            LOG.warning(
                "No spot_config set in configs of ComposeX File. Setting to defaults"
            )
            self.spot_config = self.default_spot_config
