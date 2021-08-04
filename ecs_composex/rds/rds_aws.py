#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


"""
Module to scan and find the DB and Secret for Lookup of x-rds
"""

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import (
    define_lookup_role_from_info,
    find_aws_resource_arn_from_tags_api,
)
from ecs_composex.iam import ROLE_ARN_ARG
from ecs_composex.rds.rds_params import DB_SECRET_T


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
    allowed_keys = ["secret", "cluster", "db", ROLE_ARN_ARG]
    rds_specific = ["secret", "cluster", "db"]
    if not all(key in allowed_keys for key in lookup.keys()):
        raise KeyError("Lookup section allows only", allowed_keys, "Got", lookup.keys())
    if not any(key in ["cluster", "db"] for key in lookup.keys()):
        raise KeyError("You must define at least one of", ["cluster", "db"])
    for key_name in lookup:
        if key_name in rds_specific and not isinstance(lookup[key_name], dict):
            raise TypeError(
                f"{key_name} is of type", type(lookup[key_name]), "Expected", dict
            )
        elif key_name == ROLE_ARN_ARG and not isinstance(lookup[ROLE_ARN_ARG], str):
            raise TypeError(f"{ROLE_ARN_ARG} must be of type", str)
    if keyisset("cluster", lookup) and keyisset("db", lookup):
        raise KeyError(
            f"{db_name} - You can only search for RDS cluster or db but not both at the same time."
        )
    if not keyisset("secret", lookup):
        LOG.warning(
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


def handle_secret(lookup, db_config, session):
    """
    Function to identify and update definition with secret if defined and found

    :param dict lookup: The Lookup definition for DB
    :param session: Boto3 session for clients
    :type session: boto3.session.Session
    :param dict db_config:
    :return:
    """
    if keyisset("secret", lookup):
        secret_arn = find_aws_resource_arn_from_tags_api(
            lookup["secret"], session, "secretsmanager:secret"
        )
        if secret_arn and db_config:
            db_config.update({DB_SECRET_T: secret_arn})


def patch_db_vs_cluster(db_config, res_type):
    """
    Function to match the difference in structure for rds:db and rds:cluster

    :param dict db_config: The DB config retrieved
    :param str res_type: The RDS resource type, db|cluster
    :return:
    """
    if (
        res_type == "db"
        and keyisset("Endpoint", db_config)
        and keyisset("Port", db_config["Endpoint"])
    ):
        db_config["Port"] = db_config["Endpoint"]["Port"]


def lookup_rds_resource(lookup, session):
    """
    Function to find the DB in AWS account

    :param dict lookup: The Lookup definition for DB
    :param boto3.session.Session session: Boto3 session for clients
    :return:
    """
    rds_types = {
        "rds:db": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:rds:[\w-]+:[0-9]{12}:db:)([\S]+)$"
        },
        "rds:cluster": {
            "regexp": r"(?:^arn:aws(?:-[a-z]+)?:rds:[\w-]+:[0-9]{12}:cluster:)([\S]+)$"
        },
    }
    res_type = None
    if keyisset("cluster", lookup):
        res_type = "cluster"
    elif keyisset("db", lookup):
        res_type = "db"
    lookup_session = define_lookup_role_from_info(lookup, session)
    db_arn = find_aws_resource_arn_from_tags_api(
        lookup[res_type], lookup_session, f"rds:{res_type}", types=rds_types
    )
    if not db_arn:
        return None
    db_config = return_db_config(db_arn, lookup_session, res_type)
    handle_secret(lookup, db_config, lookup_session)
    patch_db_vs_cluster(db_config, res_type)

    LOG.debug(db_config)
    return db_config
