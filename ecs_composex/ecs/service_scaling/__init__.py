# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Package to help generate target scaling policies for given alarms.
"""


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.ecs.ecs_family import ComposeFamily

from copy import deepcopy
from json import dumps

from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import (
    AWS_ACCOUNT_ID,
    AWS_PARTITION,
    AWS_URL_SUFFIX,
    Ref,
    Select,
    Split,
    Sub,
    applicationautoscaling,
)
from troposphere_awscommunity_applicationautoscaling_scheduledaction import (
    ScalableTargetAction,
    ScheduledAction,
)

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.cfn_params import STACK_ID_SHORT
from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import add_resource
from ecs_composex.ecs import ecs_params

from .helpers import define_tracking_target_configuration, merge_family_services_scaling


class ServiceScaling:
    """
    Class to group the configuration for Service scaling

    :ivar ComposeFamily family:
    """

    defined = False
    target_scaling_keys = ["CpuTarget", "MemoryTarget", "TgtTargetsCount"]

    def __init__(self, family: ComposeFamily):
        self.family = family
        configuration = merge_family_services_scaling(family.services)
        self.scaling_range = None
        self.target_scaling = None
        self.scalable_target = None
        self.scaling_policies = []
        self.scheduled_actions: list = set_else_none("ScheduledActions", configuration)
        self.replicas = max(service.replicas for service in family.services)
        self.defined = False
        if not keyisset("Range", configuration):
            return
        self.defined = True
        if self.replicas != ecs_params.SERVICE_COUNT.Default:
            self.family.stack.Parameters.update(
                {ecs_params.SERVICE_COUNT.title: self.replicas}
            )
        self.scaling_range = configuration["Range"]
        for key in self.target_scaling_keys:
            if keyisset("TargetScaling", configuration) and keyisset(
                key, configuration["TargetScaling"]
            ):
                self.target_scaling = configuration["TargetScaling"]

    def __repr__(self):
        return dumps(
            {"Range": self.scaling_range, "TargetScaling": self.target_scaling},
            indent=2,
        )

    @property
    def replicas(self):
        if self.family.stack and keyisset(
            ecs_params.SERVICE_COUNT.title, self.family.stack.Parameters
        ):
            return self.family.stack.Parameters[ecs_params.SERVICE_COUNT.title]
        else:
            return max(service.replicas for service in self.family.services)

    @replicas.setter
    def replicas(self, value):
        if self.family.stack:
            self.family.stack.Parameters.update({ecs_params.SERVICE_COUNT.title: value})

    def create_scalable_target(self):
        """
        Method to automatically create a scalable target
        """
        if self.scaling_range:
            self.scalable_target = applicationautoscaling.ScalableTarget(
                ecs_params.SERVICE_SCALING_TARGET,
                MaxCapacity=self.scaling_range["max"],
                MinCapacity=self.scaling_range["min"],
                ScalableDimension="ecs:service:DesiredCount",
                ServiceNamespace="ecs",
                RoleARN=Sub(
                    f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:role/"
                    f"ecs.application-autoscaling.${{{AWS_URL_SUFFIX}}}/"
                    "AWSServiceRoleForApplicationAutoScaling_ECSService"
                ),
                ResourceId=Sub(
                    f"service/${{{ecs_params.CLUSTER_NAME.title}}}/"
                    f"${{{self.family.ecs_service.ecs_service.title}.Name}}"
                ),
                SuspendedState=applicationautoscaling.SuspendedState(
                    DynamicScalingInSuspended=False
                ),
            )
        else:
            self.scalable_target = applicationautoscaling.ScalableTarget(
                ecs_params.SERVICE_SCALING_TARGET,
                MaxCapacity=self.replicas,
                MinCapacity=self.replicas,
                ScalableDimension="ecs:service:DesiredCount",
                ServiceNamespace="ecs",
                RoleARN=Sub(
                    f"arn:${{{AWS_PARTITION}}}:iam::${{{AWS_ACCOUNT_ID}}}:role/"
                    f"ecs.application-autoscaling.${{{AWS_URL_SUFFIX}}}/"
                    "AWSServiceRoleForApplicationAutoScaling_ECSService"
                ),
                ResourceId=Sub(
                    f"service/${{{ecs_params.CLUSTER_NAME.title}}}/"
                    f"${{{self.family.ecs_service.ecs_service.title}.Name}}"
                ),
                SuspendedState=applicationautoscaling.SuspendedState(
                    DynamicScalingInSuspended=False
                ),
            )
        if (
            self.scalable_target
            and self.scalable_target.title not in self.family.template.resources
        ):
            add_resource(self.family.template, self.scalable_target)

    def add_target_scaling(self) -> None:
        """
        Adds target scaling rules
        """
        if self.scalable_target and self.target_scaling:
            if keyisset("CpuTarget", self.target_scaling):
                policy = applicationautoscaling.ScalingPolicy(
                    "ServiceCpuTrackingPolicy",
                    ScalingTargetId=Ref(self.scalable_target),
                    PolicyName="CpuTrackingScalingPolicy",
                    PolicyType="TargetTrackingScaling",
                    TargetTrackingScalingPolicyConfiguration=define_tracking_target_configuration(
                        self.target_scaling, "cpu"
                    ),
                )
            elif keyisset("MemoryTarget", self.target_scaling):
                policy = applicationautoscaling.ScalingPolicy(
                    "ServiceMemoryTrackingPolicy",
                    ScalingTargetId=Ref(self.scalable_target),
                    PolicyName="MemoryTrackingScalingPolicy",
                    PolicyType="TargetTrackingScaling",
                    TargetTrackingScalingPolicyConfiguration=define_tracking_target_configuration(
                        self.target_scaling, "memory"
                    ),
                )
            else:
                policy = None
            if policy:
                self.scaling_policies.append(policy)
                if (
                    self.family.template
                    and policy.title not in self.family.template.resources
                ):
                    add_resource(self.family.template, policy)

    def add_scheduled_actions(self) -> None:
        """Sets the scheduled actions"""
        if not self.scalable_target or not self.scheduled_actions:
            LOG.debug(f"services.{self.family.name}.x-scaling - No ScheduledActions")
            return
        for _count, _action in enumerate(self.scheduled_actions):
            action = deepcopy(_action)
            target_capacity = ScalableTargetAction(**action["ScalableTargetAction"])
            del action["ScalableTargetAction"]
            cfn_action_title = NONALPHANUM.sub("", action["ScheduledActionName"])
            macro_parameters = set_else_none("MacroParameters", action)
            if macro_parameters:
                del action["MacroParameters"]
                if keyisset("AddServiceName", macro_parameters):
                    action["ScheduledActionName"] = Sub(
                        f"${{{self.family.ecs_service.ecs_service.title}.Name}}."
                        + action["ScheduledActionName"]
                    )
                elif keyisset("AddRandomId", macro_parameters):
                    action["ScheduledActionName"] = Sub(
                        "${STACK_ID_SHORT}" + action["ScheduledActionName"],
                        STACK_ID_SHORT,
                    )
            action.update(
                {
                    "ResourceId": Select(0, Split("|", Ref(self.scalable_target))),
                    "ScalableDimension": Select(
                        1, Split("|", Ref(self.scalable_target))
                    ),
                    "ServiceNamespace": Select(
                        2, Split("|", Ref(self.scalable_target))
                    ),
                }
            )
            scheduled_action = add_resource(
                self.family.template,
                ScheduledAction(
                    f"{self.family.logical_name}ScheduledAction{cfn_action_title}",
                    ScalableTargetAction=target_capacity,
                    **action,
                ),
            )
            LOG.debug(
                f"services.{self.family.name} - Added ScheduledAction {scheduled_action.title}"
            )
