﻿#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the XStack SSM
"""

from troposphere import GetAtt, Ref

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack

from ecs_composex.ssm_parameter.ssm_params import MOD_KEY, RES_KEY, SSM_PARAM_NAME, SSM_PARAM_TYPE


class SsmParamter(XResource):
    """
    Class to represent a SQS Queue
    """

    # policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            SSM_PARAM_NAME: (self.logical_name, self.cfn_resource, Ref, None, "Url"),
            SSM_PARAM_TYPE: (
                f"{self.logical_name}{SSM_PARAM_TYPE.return_value}",
                self.cfn_resource,
                GetAtt,
                SSM_PARAM_TYPE.return_value,
                "Arn",
            )
        }


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, SsmParamter, RES_KEY, MOD_KEY)
        new_queues = [
            queue
            for queue in settings.compose_content[RES_KEY].values()
            if not queue.lookup and not queue.use
        ]
        if new_queues:
            template = build_template("Parent template for SQS in ECS Compose-X")
            super().__init__(title, stack_template=template, **kwargs)
            render_new_queues(settings, new_queues, self, template)
        else:
            self.is_void = True

        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
