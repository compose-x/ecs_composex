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


from troposphere import Ref, GetAtt

from ecs_composex.common import keyisset, build_template
from ecs_composex.common.outputs import ComposeXOutput
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.kms.kms_params import (
    RES_KEY,
    KMS_KEY_ID_T,
    KMS_KEY_ARN_T,
)

CFN_MAX_OUTPUTS = 50


def create_kms_template(settings):
    """

    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    mono_template = False
    template = build_template("Root template for KMS")
    if not keyisset(RES_KEY, settings.compose_content):
        return
    keys = settings.compose_content[RES_KEY]
    if len(list(keys.keys())) <= CFN_MAX_OUTPUTS:
        mono_template = True

    for key_name in keys:
        key = keys[key_name]
        key.define_kms_key()
        if key:
            values = [
                (KMS_KEY_ARN_T, "Arn", GetAtt(key.cfn_resource, "Arn")),
                (KMS_KEY_ID_T, "Name", Ref(key.cfn_resource)),
            ]
            outputs = ComposeXOutput(key.cfn_resource, values, True)
            if mono_template:
                template.add_resource(key.cfn_resource)
                key.handle_key_settings(template)
                template.add_output(outputs.outputs)
            elif not mono_template:
                key_template = build_template(
                    f"Template for KMS key {key.logical_name}"
                )
                key_template.add_resource(key.cfn_resource)
                key.handle_key_settings(key_template)
                key_template.add_output(outputs.outputs)
                key_stack = ComposeXStack(key.logical_name, stack_template=key_template)
                template.add_resource(key_stack)
    return template
