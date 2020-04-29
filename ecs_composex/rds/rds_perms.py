# -*- coding: utf-8 -*-
"""
Module to provide services with access to the RDS databases.
"""

from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.common import cfn_conditions, LOG
from ecs_composex.rds.rds_params import (
    DB_EXPORT_PORT_T,
    DB_EXPORT_PREFIX_T,
    DB_EXPORT_SECRET_ARN_T,
    DB_EXPORT_SECRET_NAME_T,
)


def generate_rds_export_strings(db_name):
    """
    Function to generate the CFN export strings
    :return:
    """
    db_strings = {
        DB_EXPORT_PORT_T: f"${{{ROOT_STACK_NAME_T}}}-{db_name}-{DB_EXPORT_PORT_T}",
        DB_EXPORT_PREFIX_T: f"{{{ROOT_STACK_NAME_T}}}-{db_name}-{DB_EXPORT_PREFIX_T}",
        DB_EXPORT_SECRET_ARN_T: f"{{{ROOT_STACK_NAME_T}}}-{db_name}-{DB_EXPORT_SECRET_ARN_T}",
        DB_EXPORT_SECRET_NAME_T: f"{{{ROOT_STACK_NAME_T}}}-{db_name}-{DB_EXPORT_SECRET_NAME_T}",
    }
    return db_strings


def generate_rds_permissions():
    """
    Function to generate the IAM policy to use for the ECS Execution role to get access to the RDS secrets
    :return:
    """


def generate_rds_envvars():
    """
    Function to generate ENV Vars for ECS Service
    :return:
    """
