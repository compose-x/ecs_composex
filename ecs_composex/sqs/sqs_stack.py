#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module for the XStack SQS
"""

from troposphere import GetAtt, Ref

from ecs_composex.common import build_template
from ecs_composex.common.compose_resources import XResource, set_resources
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.sqs.sqs_params import MOD_KEY, RES_KEY, SQS_ARN, SQS_NAME, SQS_URL
from ecs_composex.sqs.sqs_perms import get_access_types
from ecs_composex.sqs.sqs_template import render_new_queues


class Queue(XResource):
    """
    Class to represent a SQS Queue
    """

    policies_scaffolds = get_access_types()

    def init_outputs(self):
        self.output_properties = {
            SQS_URL: (self.logical_name, self.cfn_resource, Ref, None, "Url"),
            SQS_ARN: (
                f"{self.logical_name}{SQS_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                SQS_ARN.return_value,
                "Arn",
            ),
            SQS_NAME: (
                f"{self.logical_name}{SQS_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                SQS_NAME.return_value,
                "QueueName",
            ),
        }


class XStack(ComposeXStack):
    """
    Class to handle SQS Root stack related actions
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, Queue, RES_KEY, MOD_KEY)
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
