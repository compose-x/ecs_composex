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
Module to scan and find the DB and Secret for Lookup of x-rds
"""

from ecs_composex.common import keyisset, LOG


def validate_rds_settings(lookup_properties):
    """
    Function to validate RDS properties for lookup
    :param dict lookup_properties:
    :raises: KeyError, TypeError
    """
    rds_allowed_keys = {"Name": str, "Tags": list}
    for key_name in ["cluster", "db", "secret"]:
        if keyisset(key_name, lookup_properties):
            for property_name in lookup_properties[key_name]:
                if property_name not in rds_allowed_keys.keys():
                    raise KeyError(
                        f"{property_name} not allowed for cluster. Expected",
                        rds_allowed_keys.keys(),
                    )
                elif property_name in rds_allowed_keys.keys() and not isinstance(
                    lookup_properties[key_name][property_name],
                    rds_allowed_keys[property_name],
                ):
                    raise TypeError(
                        f"{property_name} is of type",
                        type(lookup_properties[key_name][property_name]),
                        "Expected",
                        rds_allowed_keys[property_name],
                    )


def validate_rds_lookup(lookup):
    """
    Function to validate the lookup settings are correct
    :param lookup: The DB Lookup property
    :type lookup: dict
    :return:
    :raises: KeyError
    """
    if not lookup or not isinstance(lookup, dict):
        raise TypeError(
            "The Lookup section for RDS must be an object/dictionary. Got", type(lookup)
        )
    allowed_keys = ["secret", "cluster", "db"]
    if not all(key in allowed_keys for key in lookup.keys()):
        raise KeyError("Lookup section allows only", allowed_keys, "Got", lookup.keys())
    if not any(key in ["cluster", "db"] for key in lookup.keys()):
        raise KeyError("You must define at least one of", ["cluster", "db"])
    for key_name in lookup:
        if not isinstance(lookup[key_name], dict):
            raise TypeError(
                f"{key_name} is of type", type(lookup[key_name]), "Expected", dict
            )
    if keyisset("cluster", lookup) and keyisset("db", lookup):
        raise KeyError(
            "You can only search for RDS cluster or db but not both at the same time."
        )
    if not keyisset("secret", lookup):
        LOG.warn(
            "You did not define the secret to use, therefore we cannot assign that to the container."
            " You might encounter authentication issues."
        )
    validate_rds_settings(lookup)


def find_rds_db(info, settings):
    """
    Function to find the RDS DB based on info

    :param info:
    :type info: dict
    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """


def find_rds_cluster(info, settings):
    """
    Function to find the RDS Cluster based on info

    :param info:
    :type info: dict
    :param settings:
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """
    cluster_arn_re = ""


def lookup_rds_resource(lookup, settings):
    """
    Function to find the DB in AWS account

    :param lookup: The Lookup definition for DB
    :type lookup: dict
    :param settings: The ComposeX execution settings
    :type settings: ecs_composex.common.settings.ComposeXSettings
    :return:
    """
    if keyisset("cluster", lookup):
        find_rds_cluster(lookup["cluster"], settings)
    elif keyisset("db", lookup):
        find_rds_db(lookup["db"], settings)
