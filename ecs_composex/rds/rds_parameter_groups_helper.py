# -*- coding: utf-8 -*-
"""
Helper to generate default parameter group settings from engine name and version
"""
import boto3
from ecs_composex.common import LOG


def get_db_engine_settings(db_engine_name, db_engine_version, serverless=False):
    """
    Function to return just the details about that DB Engine Version
    """
    LOG.info(f"Looking for the family of {db_engine_name}-{db_engine_version}")
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

    if db_family.startswith("aurora"):
        LOG.info("Aurora based instance")
        LOG.info(f"Looking for parameters for {db_family}")
        return get_db_cluster_engine_parameter_group_defaults(db_family)
    else:
        return None
