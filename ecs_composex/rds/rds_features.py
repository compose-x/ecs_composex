#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>


"""
Module to handle RDS Features definition
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import AWS_NO_VALUE, AWS_STACK_NAME, GetAtt, Ref, Sub
from troposphere.iam import Role as IamRole
from troposphere.rds import DBClusterRole

from ecs_composex.common import LOG
from ecs_composex.iam import define_iam_policy, service_role_trust_policy
from ecs_composex.rds.rds_features_define import (
    define_s3_export_feature_policy,
    define_s3_import_feature_policy,
)

S3_KEY = "x-s3"


def validate_rds_features(features_list, db_family):
    """
    Function to validate the features listed are supported by the given family.

    :param features_list:
    :param db_family:
    :return:
    """


def validate_features_content(data):
    """
    Function to ensure the data given in compose file is valid for S3/MacroParameters/IamAccess

    :param dict allowed_keys:
    :param dict data:
    :return:
    """
    feature_structure = {"Name": (str, None), "Resources": (list, None)}
    for feature in data:
        for name, rtype in feature_structure.items():
            if not keyisset(name, feature):
                raise KeyError(f"Features requires {name}. Got", feature.keys())
            elif not isinstance(feature[name], rtype[0]):
                raise TypeError(
                    f"Feature property {name} is of type",
                    type(feature),
                    "Expected",
                    rtype[0],
                )


def define_associated_roles(db):
    """
    Function to define the AssociatedRoles, either present or empty
    :param ecs_composex.rds.rds_stack.RdsDb db:
    :return: the list of Associated Roles
    :rtype: list
    """
    if db.cfn_resource and hasattr(db.cfn_resource, "AssociatedRoles"):
        LOG.warning(
            "The db properties already had AssociatedRoles defined."
            " Only will add ones without the feature already defined"
        )
        roles = getattr(db.cfn_resource, "AssociatedRoles")
    else:
        roles = []
    return roles


def add_rds_features(settings, stack, db, features, db_template, boundary):
    """
    Function to add AssociatedRoles and Features if not already defined in the DB properties for that feature.
    """
    features_settings = {
        "s3Import": define_s3_import_feature_policy,
        "s3Export": define_s3_export_feature_policy,
        "Lambda": None,
        "SageMaker": None,
        "Comprehend": None,
    }
    validate_features_content(features)
    roles = define_associated_roles(db)
    to_add = [
        feature
        for feature in features
        if feature["Name"] not in [role.FeatureName for role in roles]
    ]
    excluded = [
        feature
        for feature in features
        if feature["Name"] in [role.FeatureName for role in roles]
    ]
    if excluded:
        LOG.warning(
            f"Features {excluded} are not being processed as already defined in AssociatedRoles of the DB properties"
        )
    if not to_add:
        LOG.warning("No features were found to be added at all!!")
        return
    policies = []
    iam_role = IamRole(
        f"{db.logical_name}FeaturesIamRole",
        AssumeRolePolicyDocument=service_role_trust_policy("rds"),
        Description=Sub(
            f"{db.logical_name} RDS Features IAM Role in ${{{AWS_STACK_NAME}}}"
        ),
        Policies=policies,
        PermissionsBoundary=boundary,
        MaxSessionDuration=3600,
    )
    features_definition = []
    for feature in to_add:
        if feature["Name"] not in features_settings.keys() or not (
            feature["Name"] in features_settings.keys()
            and features_settings[feature["Name"]]
        ):
            LOG.warning(
                f"The feature {feature['Name']} is not currently supported. Sorry."
            )
        policies.append(
            features_settings[feature["Name"]](
                settings, stack, db, feature["Resources"], db_template
            )
        )
        features_definition.append(
            DBClusterRole(FeatureName=feature["Name"], RoleArn=GetAtt(iam_role, "Arn"))
        )
    db_template.add_resource(iam_role)
    if policies and not hasattr(db.cfn_resource, "AssociatedRoles"):
        setattr(db.cfn_resource, "AssociatedRoles", features_definition)


def apply_extra_parameters(settings, stack, db, db_template):
    """
    Function to add extra parameters set in MacroParameters post creation of the DB resource from properties

    :param ecs_composex.rds.rds_stack.Rds db db:
    :param troposphere.Template db_template:
    :return:
    """
    if not db.parameters:
        return
    permissions_boundary = Ref(AWS_NO_VALUE)
    if keyisset("PermissionsBoundary", db.parameters):
        permissions_boundary = define_iam_policy(db.parameters["PermissionsBoundary"])
    extra_parameters = {"RdsFeatures": (list, add_rds_features)}
    for name, config in extra_parameters.items():
        if not keyisset(name, db.parameters):
            LOG.debug(
                f"Feature {name} has not been set in compose file. {db.parameters}"
            )
        if (
            keyisset(name, db.parameters)
            and isinstance(db.parameters[name], config[0])
            and config[1]
        ):
            config[1](
                settings,
                stack,
                db,
                db.parameters[name],
                db_template,
                permissions_boundary,
            )
        elif keyisset(name, db.parameters) and not isinstance(
            db.parameters[name], config[0]
        ):
            LOG.error(
                f"The property {name} is of type {type(db.parameters[name])}. Expected {config[0]}. Skipping"
            )
