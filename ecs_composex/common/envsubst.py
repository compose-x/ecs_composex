#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to do a better env variables handling.
"""

import os
import re

ENV_VAR_REGEXP = r"(?<!\\)\$(\w+|\{(?!AWS::)([^}]*)\})"
SPECIAL_INTERPOLATION = r"(?<!\\)(\$(\{(((?!AWS::)[^}]+)(\:[+-=]{1}))([^}]+)\}))"
IF_UNDEFINED = r":-"
IF_DEFINED = r":+"


def expandvars(path, default=None, skip_escaped=True):
    """
    Expand environment variables of form $var and ${var}.
       If parameter 'skip_escaped' is True, all escaped variable references
       (i.e. preceded by backslashes) are skipped.
       Unknown variables are set to 'default'. If 'default' is None,
       they are left unchanged.
    """

    def replace_var(match):
        if re.match(SPECIAL_INTERPOLATION, match.group(0)):
            groups = re.findall(SPECIAL_INTERPOLATION, match.group(0))
            if groups[0][-2] == IF_UNDEFINED:
                return os.environ.get(groups[0][-3]) or expandvars(
                    groups[0][-1], default, skip_escaped
                )
            elif groups[0][-2] == IF_DEFINED:
                return expandvars(groups[0][-1])
        return os.environ.get(
            match.group(2) or match.group(1),
            match.group(0) if default is None else default,
        )

    re_string = (r"(?<!\\)" if skip_escaped else "") + r"\$(\w+|\{(?!AWS::)([^}]*)\})"
    return re.sub(re_string, replace_var, path)
