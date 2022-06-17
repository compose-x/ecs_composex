#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import secrets
import string

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWS_NO_VALUE, Ref, applicationautoscaling
from troposphere.applicationautoscaling import (
    ScalingPolicy,
    StepAdjustment,
    StepScalingPolicyConfiguration,
)

from ecs_composex.common.logging import LOG
from ecs_composex.common.troposphere_tools import *
from ecs_composex.ecs.ecs_params import SERVICE_SCALING_TARGET


def validate_steps_definition(steps, unordered):
    """
    Validates that the steps definition is correct

    :param list steps: list of step definitions
    :param list unordered: list of steps, unordered.
    """
    allowed_keys = ["LowerBound", "UpperBound", "Count"]
    for step_def in steps:
        if not all(key in allowed_keys for key in step_def.keys()):
            raise KeyError(
                "Step definition only allows",
                allowed_keys,
                "Got",
                step_def.keys(),
            )
        if (
            keyisset("UpperBound", step_def)
            and step_def["LowerBound"] >= step_def["UpperBound"]
        ):
            raise ValueError(
                "The LowerBound value must strictly lower than the upper bound",
                step_def,
            )
        unordered.append(step_def)


def rectify_scaling_steps(cfn_steps):
    """
    Function to rectify settings to avoid errors

    :param list cfn_steps:
    """
    if hasattr(cfn_steps[-1], "MetricIntervalUpperBound") and not isinstance(
        getattr(cfn_steps[-1], "MetricIntervalUpperBound"), Ref
    ):
        LOG.warning("The last upper bound shall not be set. Deleting value to comply}")
        setattr(cfn_steps[-1], "MetricIntervalUpperBound", Ref(AWS_NO_VALUE))
    if cfn_steps[0].MetricIntervalLowerBound == 0:
        LOG.warning(
            "You defined the lower bound to 0. To enable alarm threshold we are setting it to 1"
        )
        setattr(cfn_steps[0], "MetricIntervalLowerBound", 1)


def define_step_adjustment(pre_upper, ordered, cfn_steps):
    for step_def in ordered:
        if pre_upper and not int(step_def["LowerBound"]) >= pre_upper:
            raise ValueError(
                f"The value for lower bound is {step_def['LowerBound']},"
                f"which is higher than the previous UpperBound, {pre_upper}"
            )
        cfn_steps.append(
            StepAdjustment(
                MetricIntervalLowerBound=int(step_def["LowerBound"]),
                MetricIntervalUpperBound=int(step_def["UpperBound"])
                if keyisset("UpperBound", step_def)
                else Ref(AWS_NO_VALUE),
                ScalingAdjustment=int(step_def["Count"]),
            )
        )
        pre_upper = (
            int(step_def["UpperBound"]) if keyisset("UpperBound", step_def) else None
        )


def generate_scaling_out_steps(steps, target):
    """
    Function to generate the scaling steps

    :param list steps:
    :param tropsphere.applicationautoscaling.ScalingTarget target: The defined max in the Scalable Target
    :return:
    """
    unordered = []
    validate_steps_definition(steps, unordered)
    ordered = sorted(unordered, key=lambda i: i["LowerBound"])
    if target and ordered[-1]["Count"] > target.MaxCapacity:
        LOG.warning(
            f"The current maximum in your Range is {target.MaxCapacity} whereas you defined {ordered[-1]['Count']}"
            " for step scaling. Adjusting to step scaling max."
        )
        setattr(target, "MaxCapacity", ordered[-1]["Count"])
    cfn_steps = []
    pre_upper = 0
    define_step_adjustment(pre_upper, ordered, cfn_steps)
    rectify_scaling_steps(cfn_steps)
    return cfn_steps


def generate_alarm_scaling_out_policy(
    service_name, service_template, scaling_def, scaling_source=None
):
    """
    Function to create the scaling out policy based on steps

    :param str service_name: The name of the service/family
    :param troposphere.Template service_template:
    :param dict scaling_def:
    :param str scaling_source:
    :return: The scaling out policy
    :rtype: ScalingPolicy
    """
    if not keyisset("Steps", scaling_def):
        raise KeyError("No steps were defined in the scaling definition", scaling_def)
    steps_definition = scaling_def["Steps"]
    length = 6
    if not scaling_source:
        scaling_source = "".join(
            secrets.choice(string.ascii_lowercase) for _ in range(length)
        )
    scalable_target = service_template.resources[SERVICE_SCALING_TARGET]
    step_adjustments = generate_scaling_out_steps(
        steps_definition, target=scalable_target
    )
    policy = ScalingPolicy(
        f"ScalingOutPolicy{scaling_source}{service_name}",
        PolicyName=f"ScalingOutPolicy{scaling_source}{service_name}",
        PolicyType="StepScaling",
        ScalingTargetId=Ref(SERVICE_SCALING_TARGET),
        ServiceNamespace="ecs",
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ExactCapacity",
            StepAdjustments=step_adjustments,
            Cooldown=60
            if not keyisset("ScaleOutCooldown", scaling_def)
            or not (isinstance(scaling_def["ScaleOutCooldown"], int))
            else scaling_def["ScaleOutCooldown"],
        ),
    )
    add_resource(service_template, policy, True)
    return policy


def reset_to_zero_policy(
    service_name, service_template, scaling_def, scaling_source=None
):
    """
    Defines a policy allowing to reset to 0 containers.

    :param service_name:
    :param service_template:
    :param dict scaling_def:
    :param scaling_source:
    :return:
    """
    length = 6
    if not scaling_source:
        scaling_source = "".join(
            secrets.choice(string.ascii_lowercase) for _ in range(length)
        )
    policy = ScalingPolicy(
        f"ScalingInPolicy{scaling_source}{service_name}",
        PolicyName=f"ScalingInPolicy{scaling_source}{service_name}",
        PolicyType="StepScaling",
        ScalingTargetId=Ref(SERVICE_SCALING_TARGET),
        ServiceNamespace="ecs",
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ExactCapacity",
            Cooldown=60
            if not keyisset("ScaleInCooldown", scaling_def)
            or not (isinstance(scaling_def["ScaleInCooldown"], int))
            else scaling_def["ScaleInCooldown"],
            StepAdjustments=[
                StepAdjustment(
                    MetricIntervalUpperBound=0,
                    ScalingAdjustment=0,
                ),
            ],
        ),
    )
    add_resource(service_template, policy, True)
    return policy


def handle_range(config, key, new_range):
    """
    Function to handle Range.
    """
    new_min = int(new_range.split("-")[0])
    new_max = int(new_range.split("-")[1])
    if not config[key]:
        config[key] = {"min": new_min, "max": new_max}
    else:
        config[key]["min"] = min(config[key]["min"], new_min)
        config[key]["max"] = max(config[key]["max"], new_max)


def handle_defined_target_scaling_props(prop, config, key, new_config):
    if prop[1] is int:
        config[key][prop[0]] = min(config[key][prop[0]], new_config[prop[0]])
    elif (
        prop[1] is bool
        and not keyisset(prop[0], config[key])
        and keyisset(prop[0], new_config)
    ):
        LOG.warning(f"At least one service enabled {prop[0]}. Enabling for all")
        config[key][prop[0]] = True


def define_new_config(config, key, new_config):
    valid_keys = [
        "CpuTarget",
        "MemoryTarget",
        "DisableScaleIn",
        "TgtTargetsCount",
        "ScaleInCooldown",
        "ScaleOutCooldown",
    ]
    for prop in valid_keys:
        if keypresent(prop, config[key]) and keypresent(prop, new_config):
            handle_defined_target_scaling_props(prop, config, key, new_config)
        elif not keypresent(prop, config[key]) and keypresent(prop, new_config):
            config[key][prop] = new_config[prop]


def handle_target_scaling(config, key, new_config):
    """
    Function to handle merge of target tracking config
    """

    if not config[key]:
        config[key] = new_config
    else:
        define_new_config(config, key, new_config)


def handle_defined_x_aws_autoscaling(configs, service):
    """
    Function to sort out existing or not x-aws-autoscaling in the deploy section

    :param list configs:
    :param ecs_composex.common.compose_services.ComposeService service:
    :return:
    """
    if keyisset("deploy", service.definition) and keyisset(
        "x-aws-autoscaling", service.definition["deploy"]
    ):
        config = service.definition["deploy"]["x-aws-autoscaling"]
        min_count = 1 if not keypresent("min", config) else int(config["min"])
        max_count = 1 if not keypresent("max", config) else int(config["max"])
        if not service.x_scaling:
            service.x_scaling = {"Range": f"{min_count}-{max_count}"}
            if keyisset("cpu", config):
                service.x_scaling.update(
                    {"TargetScaling": {"CpuTarget": int(config["cpu"])}}
                )
        elif service.x_scaling:
            LOG.warning(
                f"Detected both x-aws-autoscaling and x-scaling for {service.name}. Priority goes to x-scaling"
            )
        configs.append(service.x_scaling)
    elif service.x_scaling:
        LOG.debug("No x-aws-autoscaling detected, proceeding as usual")
        configs.append(service.x_scaling)


def merge_family_services_scaling(services):
    x_scaling = {
        "Range": None,
        "TargetScaling": {
            "DisableScaleIn": False,
            "ScaleInCooldown": 300,
            "ScaleOutCooldown": 60,
        },
    }
    x_scaling_configs = []
    for service in services:
        handle_defined_x_aws_autoscaling(x_scaling_configs, service)
    valid_keys = [
        ("Range", str, handle_range),
        ("TargetScaling", dict, handle_target_scaling),
    ]
    for key in valid_keys:
        for config in x_scaling_configs:
            if (
                keyisset(key[0], config)
                and isinstance(config[key[0]], key[1])
                and key[2]
            ):
                key[2](x_scaling, key[0], config[key[0]])
    return x_scaling


def define_tracking_target_configuration(target_scaling_config, config_key):
    """
    Function to create the configuration for target tracking scaling

    :param dict target_scaling_config:
    :param str config_key:
    :return:
    """
    settings = {
        "cpu": {
            "key": "CpuTarget",
            "property": "ECSServiceAverageCPUUtilization",
        },
        "memory": {
            "key": "MemoryTarget",
            "property": "ECSServiceAverageMemoryUtilization",
        },
        "targets": {
            "key": "TgtTargetsCount",
            "property": "ALBRequestCountPerTarget",
        },
    }
    if config_key not in settings.keys():
        raise KeyError(config_key, "Is invalid. Expected one of", settings.keys())
    specification = applicationautoscaling.PredefinedMetricSpecification(
        PredefinedMetricType=settings[config_key]["property"]
    )

    return applicationautoscaling.TargetTrackingScalingPolicyConfiguration(
        DisableScaleIn=target_scaling_config["DisableScaleIn"],
        ScaleInCooldown=target_scaling_config["ScaleInCooldown"],
        ScaleOutCooldown=target_scaling_config["ScaleOutCooldown"],
        TargetValue=float(target_scaling_config[settings[config_key]["key"]]),
        PredefinedMetricSpecification=specification,
    )
