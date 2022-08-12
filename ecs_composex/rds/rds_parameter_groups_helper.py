# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Helper to generate default parameter group settings from engine name and version

Strip rds internal params to try and fit within 20 param limit
https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-dbparametergroup.html#cfn-rds-dbparametergroup-parameters

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from boto3.session import Session

import boto3
from botocore.exceptions import ClientError
from compose_x_common.aws import get_session
from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG


def get_db_cluster_engine_parameter_group_defaults(
    engine_family, for_aurora_cluster: bool = True, session: Session = None
):
    """
    Returns a dict of all the parameter group parameters and default values

    :parm str engine_family: Engine family we are getting the cluster settings for, i.e. aurora-mysql5.7
    """

    session = get_session(session)
    client = session.client("rds")
    try:
        if for_aurora_cluster:
            req = client.describe_engine_default_cluster_parameters(
                DBParameterGroupFamily=engine_family
            )
        else:
            req = client.describe_engine_default_parameters(
                DBParameterGroupFamily=engine_family
            )
    except ClientError as error:
        LOG.exception(error)
        return None
    params_return = {}
    if "EngineDefaults" in req.keys():
        params = req["EngineDefaults"]["Parameters"]
        for param in params:
            if (
                keyisset("ParameterValue", param)
                and r"{" not in param["ParameterValue"]
                and keyisset("IsModifiable", param)
                and not param["ParameterName"].startswith("rds.")
            ):
                params_return[param["ParameterName"]] = param["ParameterValue"]
            if param["ParameterName"] == "binlog_format":
                params_return[param["ParameterName"]] = "MIXED"
    return params_return


def get_family_from_engine_version(
    engine_name: str, engine_version: str, session: Session = None
) -> Union[str, None]:
    """
    Get the engine family from engine name and version
    """
    session = get_session(session)
    client = session.client("rds")
    try:
        req = client.describe_db_engine_versions(
            Engine=engine_name, EngineVersion=engine_version
        )
    except ClientError as error:
        LOG.error(
            f"Failed to describe DB Engine Versions for {engine_name}@{engine_version}"
        )
        LOG.exception(error)
        return None

    if not keyisset("DBEngineVersions", req):
        raise LookupError(
            "x-rds - Failed to get DB Engine version details for",
            engine_name,
            engine_version,
        )
    db_family = req["DBEngineVersions"][0]["DBParameterGroupFamily"]
    return db_family


def get_family_settings(db_family: str, session: Session = None) -> dict:
    """
    Function to get the DB family settings
    """
    session = get_session(session)
    if (
        db_family is not None
        and isinstance(db_family, str)
        and db_family.startswith("aurora")
    ):
        LOG.debug("Aurora based instance")
        LOG.debug(f"Looking for parameters for {db_family}")
        return get_db_cluster_engine_parameter_group_defaults(db_family, True, session)
    else:
        return get_db_cluster_engine_parameter_group_defaults(db_family, False, session)
