# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Global settings and variables re-used across the project
"""

from os import environ

XFILE_DEST = "ComposeXFile"
DIR_DEST = "OutputDirectory"
CFN_EXPORT_DELIMITER = environ.get("COMPOSE_X_EXPORTS_SEPARATOR", r"::")
X_KEY = r"x-"
X_AWS_KEY = r"x-aws-"
TAGS_SEPARATOR = environ.get("COMPOSE_X_TAGS_SEPARATOR", r":")
