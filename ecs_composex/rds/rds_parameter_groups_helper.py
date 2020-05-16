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

"""
Helper to generate default parameter group settings from engine name and version
"""
import boto3
from ecs_composex.common import LOG


def get_db_engine_settings(db_engine_name, db_engine_version, serverless=False):
    """
    Function to return just the details about that DB Engine Version

    :param str db_engine_name: Name of the DB Engine
    :param str db_engine_version: Version of the DB Engine to use
    :param bool serverless: Whether we are looking for an engine version that supports Serverless for RDS Aurora
    """
    LOG.debug(f"Looking for the family of {db_engine_name}-{db_engine_version}")
    client = boto3.client("rds")
    req = client.describe_db_engine_versions(
        Engine=db_engine_name, EngineVersion=db_engine_version
    )
    versions = req["DBEngineVersions"]
    if not versions:
        raise ValueError("No possible results from given parameters")
    if serverless:
        for version in versions:
            if (
                version["SupportedEngineModes"]
                and "serverless" in version["SupportedEngineModes"]
            ):
                return version
        raise ValueError(
            f"No parameters found for the {db_engine_name} {db_engine_version} supporting serverless"
        )
    return versions[0]


def get_db_cluster_engine_parameter_group_defaults(engine_family):
    """
    Returns a dict of all the parameter group parameters and default values

    :parm str engine_family: Engine family we are getting the cluster settings for, i.e. aurora-mysql5.7
    """

    client = boto3.client("rds")
    req = client.describe_engine_default_cluster_parameters(
        DBParameterGroupFamily=engine_family
    )
    params_return = {}
    if "EngineDefaults" in req.keys():
        params = req["EngineDefaults"]["Parameters"]
        for param in params:
            if (
                "ParameterValue" in param.keys()
                and "{" not in param["ParameterValue"]
                and "IsModifiable" in param.keys()
                and param["IsModifiable"] is True
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
    req = client.describe_db_engine_versions(
        Engine=engine_name, EngineVersion=engine_version
    )
    db_family = req["DBEngineVersions"][0]["DBParameterGroupFamily"]
    return db_family


def get_family_settings(db_family):
    """
    Function to get the DB family settings
    :param str db_family: The DB family
    :return: db settings or None
    :rtype: None or dict
    """
    if db_family.startswith("aurora"):
        LOG.debug("Aurora based instance")
        LOG.debug(f"Looking for parameters for {db_family}")
        return get_db_cluster_engine_parameter_group_defaults(db_family)
    else:
        return None
