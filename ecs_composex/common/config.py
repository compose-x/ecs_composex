# -*- coding: utf-8 -*-
#  ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#  Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from json import dumps

from ecs_composex.common import LOG, keyisset


class ComposeXConfig(object):
    """
    Class to parse and define configuration settings for ECS ComposeX
    """

    master_key = "x-configs"
    composex_key = "composex"
    valid_config_keys = ["network", "iam"]

    network_defaults = {
        "use_cloudmap": True,
        "is_public": False,
        "lb_type": None,
        "ext_sources": None,
    }

    def __init__(self, compose_content, service_name=None, service_configs=None):
        """
        Initializes the ComposeXConfig class
        :param compose_content: compose file content
        :type compose_content: dict
        """
        self.network = None
        self.iam = None

        self.lb_type = None
        self.healthcheck = None
        self.ext_sources = None
        self.is_public: False
        self.use_cloudmap = True
        self.boundary = None
        self.service_name = service_name if service_name else "global"

        if keyisset(self.master_key, compose_content):
            self.set_from_top_configs(compose_content)
        if service_name and isinstance(service_configs, dict):
            self.define_service_config(compose_content, service_name, service_configs)

    def __repr__(self):
        return dumps(self.__dict__)

    def init_iam(self, config):
        """
        Function to set IAM
        :return:
        """
        valid_keys = ["boundary"]
        for key_name in config.keys():
            if key_name not in valid_keys:
                raise KeyError(
                    f"{key_name} is not a valid configuration for IAM. Accepted",
                    valid_keys,
                )
            setattr(self, key_name, config[key_name])

    def init_network(self, config):
        """
        Function to define networking properties
        """
        for key_name in config.keys():
            if key_name not in self.network_defaults.keys():
                raise KeyError(
                    f"{key_name} is not a valid configuration for Networking"
                )
        for key_name in self.network_defaults:
            if key_name not in config.keys() and not hasattr(self, key_name):
                LOG.info(
                    f"Missing {key_name}. Setting to default - {self.service_name}"
                )
                setattr(self, key_name, self.network_defaults[key_name])
            elif key_name in config.keys():
                LOG.debug(f"ELSE - {key_name}- {config[key_name]}")
                setattr(self, key_name, config[key_name])

    def set_from_top_configs(self, compose_content):
        """
        Function to define the settings from global content
        :param compose_content:
        :return:
        """
        if keyisset(self.composex_key, compose_content[self.master_key]):
            for key in self.valid_config_keys:
                if keyisset(
                    key, compose_content[self.master_key][self.composex_key]
                ) and hasattr(self, f"init_{key}"):
                    init_function = getattr(self, f"init_{key}")
                    LOG.debug(init_function)
                    init_function(
                        compose_content[self.master_key][self.composex_key][key]
                    )

    def set_service_config(self, config):
        for key in self.valid_config_keys:
            if keyisset(key, config) and hasattr(self, f"init_{key}"):
                init_function = getattr(self, f"init_{key}")
                LOG.debug(init_function, config[key])
                init_function(config=config[key])

    def define_service_config(self, compose_content, service_name, config_definition):
        """
        Function to define the settings from global content
        :param config_definition:
        :param service_name:
        :param compose_content:
        :return:
        """
        if keyisset(self.master_key, compose_content) and keyisset(
            service_name, compose_content[self.master_key]
        ):
            LOG.debug(
                f"Service {service_name} has configuration in the root {self.master_key} section."
            )
            self.set_service_config(compose_content[self.master_key][service_name])
        self.set_service_config(config_definition)
