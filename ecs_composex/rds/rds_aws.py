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
from ecs_composex.common.aws import (
    find_aws_resource_arn_from_tags_api,
)


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


def validate_rds_lookup(db_name, lookup):
    """
    Function to validate the lookup settings are correct
    :param db_name: The composex resource
    :type db_name: str
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
            f"{db_name} - You can only search for RDS cluster or db but not both at the same time."
        )
    if not keyisset("secret", lookup):
        LOG.warn(
            f"You did not define the secret to use for {db_name}, therefore we cannot assign that to the container."
            " You might encounter authentication issues."
        )
    validate_rds_settings(lookup)


def return_db_config(db_arn, session, res_type):
    """
    Function to retrieve the DB information we need for services integration
    :param db_arn:
    :param session:
    :param res_type:
    :type db_arn: str
    :type session: boto3.session.Session
    :type res_type: str
    :return: the DB details
    """
    client = session.client("rds")
    try:
        if res_type == "db":
            db_r = client.describe_db_instances(DBInstanceIdentifier=db_arn)
            return db_r["DBInstances"][0]
        elif res_type == "cluster":
            db_r = client.describe_db_clusters(DBClusterIdentifier=db_arn)
            return db_r["DBClusters"][0]
    except (
        client.exceptions.DBClusterNotFoundFault,
        client.exceptions.DBInstanceNotFoundFault,
    ) as error:
        LOG.error(f"Could not fetch information about {db_arn}")
        LOG.error(error)
        return None


def lookup_rds_resource(db, session):
    """
    Function to find the DB in AWS account

    :param db: The Lookup definition for DB
    :type db: ecs_composex.rds.rds_stacks.Rds
    :param session: Boto3 session for clients
    :type session: boto3.session.Session
    :return:
    """
    res_type = None
    if keyisset("cluster", db.lookup):
        res_type = "cluster"
    elif keyisset("db", db.lookup):
        res_type = "db"
    db_arn = find_aws_resource_arn_from_tags_api(
        db.lookup[res_type], session, "rds", res_type
    )
    if not db_arn:
        return None
    db_config = return_db_config(db_arn, session, res_type)
    if keyisset("secret", db.lookup):
        secret_arn = find_aws_resource_arn_from_tags_api(
            db.lookup["secret"], session, "secretsmanager", "secret"
        )
        if secret_arn and db_config:
            db_config.update({"SecretArn": secret_arn})
    if (
        res_type == "db"
        and keyisset("Endpoint", db_config)
        and keyisset("Port", db_config["Endpoint"])
    ):
        db_config["Port"] = db_config["Endpoint"]["Port"]
    LOG.debug(db_config)
    return db_config
