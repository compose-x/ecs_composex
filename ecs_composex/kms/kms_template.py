#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020-2021  John Mille <john@lambda-my-aws.io>
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


from troposphere import MAX_OUTPUTS

from ecs_composex.common import keyisset, build_template
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms.kms_params import (
    RES_KEY,
)

CFN_MAX_OUTPUTS = MAX_OUTPUTS - 10


def create_kms_template(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = False
    template = build_template("Root template for KMS")
    if not keyisset(RES_KEY, settings.compose_content):
        return
    x_keys = settings.compose_content[RES_KEY]
    new_keys = [x_keys[key_name] for key_name in x_keys if not x_keys[key_name].lookup]
    if len(new_keys) <= CFN_MAX_OUTPUTS:
        mono_template = True

    for key in new_keys:
        key.define_kms_key()
        if key and key.cfn_resource:
            key.init_outputs()
            key.generate_outputs()
            if mono_template:
                template.add_resource(key.cfn_resource)
                key.handle_key_settings(template)
                template.add_output(key.outputs)
            elif not mono_template:
                key_template = build_template(
                    f"Template for KMS key {key.logical_name}"
                )
                key_template.add_resource(key.cfn_resource)
                key.handle_key_settings(key_template)
                key_template.add_output(key.outputs)
                key_stack = ComposeXStack(key.logical_name, stack_template=key_template)
                template.add_resource(key_stack)
    return template
