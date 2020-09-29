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
Module to do a better env variables handling.
"""

import os
import re

ENV_VAR_REGEXP = r"(?<!\\)\$(\w+|\{([^}]*)\})"
SPECIAL_INTERPOLATION = r"(?<!\\)(\$(\{(([^}]+)(\:[+-=]{1}))([^}]+)\}))"
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

    re_string = (r"(?<!\\)" if skip_escaped else "") + r"\$(\w+|\{([^}]*)\})"
    return re.sub(re_string, replace_var, path)
