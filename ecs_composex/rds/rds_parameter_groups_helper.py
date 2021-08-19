#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Helper to generate default parameter group settings from engine name and version

Strip rds internal params to try and fit within 20 param limit
https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-dbparametergroup.html#cfn-rds-dbparametergroup-parameters

"""
import boto3
from botocore.exceptions import ClientError

from ecs_composex.common import LOG


def get_db_cluster_engine_parameter_group_defaults(engine_family):
    """
    Returns a dict of all the parameter group parameters and default values

    :parm str engine_family: Engine family we are getting the cluster settings for, i.e. aurora-mysql5.7
    """

    client = boto3.client("rds")
    try:
        req = client.describe_engine_default_cluster_parameters(
            DBParameterGroupFamily=engine_family
        )
    except ClientError as error:
        LOG.error(error)
        return None
    params_return = {}
    if "EngineDefaults" in req.keys():
        params = req["EngineDefaults"]["Parameters"]
        for param in params:
            if (
                "ParameterValue" in param.keys()
                and "{" not in param["ParameterValue"]
                and "IsModifiable" in param.keys()
                and param["IsModifiable"] is True
                and not param["ParameterName"].startswith("rds.")
            ):
                params_return[param["ParameterName"]] = param["ParameterValue"]
            if param["ParameterName"] == "binlog_format":
                params_return[param["ParameterName"]] = "MIXED"
    return params_return


def get_family_from_engine_version(
    engine_name, engine_version, session=None, client=None
):
    """
    Function to get the engine family from engine name and version
    :param client: override client for boto3 call
    :type client: boto3.client
    :param session: override session for boto3 client
    :type session: boto3.session.Session
    :param engine_name: engine name, ie. aurora-mysql
    :type engine_name: str
    :param engine_version: engine version, ie. 5.7.12
    :type engine_version: str
    :return: engine_family
    :rtype: str
    """
    if not client:
        if not session:
            session = boto3.session.Session()
        client = session.client("rds")
    try:
        req = client.describe_db_engine_versions(
            Engine=engine_name, EngineVersion=engine_version
        )
    except ClientError as error:
        LOG.error(error)
        return None

    db_family = req["DBEngineVersions"][0]["DBParameterGroupFamily"]
    return db_family


def get_family_settings(db_family):
    """
    Function to get the DB family settings
    :param str db_family: The DB family
    :return: db settings or None
    :rtype: None or dict
    """
    if (
        db_family is not None
        and isinstance(db_family, str)
        and db_family.startswith("aurora")
    ):
        LOG.debug("Aurora based instance")
        LOG.debug(f"Looking for parameters for {db_family}")
        return get_db_cluster_engine_parameter_group_defaults(db_family)
    else:
        return None
