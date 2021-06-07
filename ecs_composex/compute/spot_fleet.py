#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Functions to add to the Cluster template when people want to use SpotFleet for their ECS Cluster.
"""

from troposphere import GetAtt, If, Ref, Select, Sub
from troposphere.applicationautoscaling import (
    ScalableTarget,
    ScalingPolicy,
    StepAdjustment,
    StepScalingPolicyConfiguration,
)
from troposphere.cloudwatch import Alarm
from troposphere.cloudwatch import MetricDimension as CwMetricDimension
from troposphere.ec2 import (
    LaunchTemplate,
    LaunchTemplateConfigs,
    LaunchTemplateOverrides,
    LaunchTemplateSpecification,
    SpotFleet,
    SpotFleetRequestConfigData,
)
from troposphere.iam import Role

from ecs_composex.common import LOG, build_template
from ecs_composex.compute import compute_conditions, compute_params
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.vpc import vpc_params


def add_fleet_role(template):
    """Function to create the IAM Role for the EC2 Spot Fleet

    :param template: source template to add the resources to
    :type template: troposphere.Template

    :returns: role
    :rtype: troposphere.iam.Role
    """
    role = Role(
        "IamFleetRole",
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy("spotfleet"),
        ManagedPolicyArns=[
            "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetAutoscaleRole",
            "arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole",
        ],
    )
    return role


def define_overrides(settings, lt_id, lt_version, spot_config):
    """
    From the list of AZs and the configurations set for spotfleet instances, it will generate an override that
    SpotFleet will use to diversify the compute resources.

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for execution
    :param lt_id: Launch template ID
    :param lt_version: Launch Template Version
    :param spot_config: SpotFleet configuration for pricing and instance types
    :return: configs
    :type: list
    """
    if isinstance(lt_id, LaunchTemplate):
        template_id = Ref(lt_id)
        template_version = GetAtt(lt_id, "LatestVersionNumber")
    elif not isinstance(lt_id, Ref) or not isinstance(lt_version, Ref):
        raise TypeError(
            "The launch template and/or version are of type",
            lt_id,
            lt_version,
            "Expected",
            LaunchTemplate,
            "Or",
            Ref,
        )
    else:
        template_id = lt_id
        template_version = lt_version

    overrides = []
    configs = []
    LOG.debug(spot_config)
    for count, az in enumerate(settings.aws_azs):
        LOG.debug(az)
        for itype in spot_config["spot_instance_types"]:
            overrides.append(
                LaunchTemplateOverrides(
                    SubnetId=Select(count, Ref(vpc_params.APP_SUBNETS)),
                    WeightedCapacity=spot_config["spot_instance_types"][itype][
                        "weight"
                    ],
                    InstanceType=itype,
                )
            )
    configs.append(
        LaunchTemplateConfigs(
            LaunchTemplateSpecification=LaunchTemplateSpecification(
                LaunchTemplateId=template_id, Version=template_version
            ),
            Overrides=overrides,
        )
    )
    return configs


def add_scaling_policies(template, spot_fleet, role):
    """Function to add Scaling to the SpotFleet

    :param template: source template to add the resources to
    :type template: troposphere.Template
    :param spot_fleet: the SpotFleet for reference
    :type spot_fleet: troposphere.ec2.SpotFleet
    :param role: IAM Role for the SpotFleet
    :type role: troposphere.iam.Role

    :returns: tuple(scale_in_policy, scale_out_policy)
    :rtype: tuple
    """
    target = ScalableTarget(
        f"SpotFleetScalingTarget{spot_fleet.title}",
        template=template,
        MaxCapacity=If(
            compute_conditions.MAX_IS_MIN_T,
            Ref(compute_params.MIN_CAPACITY),
            Ref(compute_params.MAX_CAPACITY),
        ),
        MinCapacity=Ref(compute_params.MIN_CAPACITY),
        ResourceId=Sub(f"spot-fleet-request/${{{spot_fleet.title}}}"),
        RoleARN=GetAtt(role, "Arn"),
        ServiceNamespace="ec2",
        ScalableDimension="ec2:spot-fleet-request:TargetCapacity",
    )

    scale_in_policy = ScalingPolicy(
        f"FleetScalingIn{spot_fleet.title}",
        template=template,
        PolicyName=Sub(f"${{{spot_fleet.title}}}ScalingIn"),
        PolicyType="StepScaling",
        ScalingTargetId=Ref(target),
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ChangeInCapacity",
            Cooldown=300,
            MetricAggregationType="Average",
            StepAdjustments=[
                StepAdjustment(MetricIntervalLowerBound=10, ScalingAdjustment="-1")
            ],
        ),
    )

    scale_out_policy = ScalingPolicy(
        f"FleetScalingOut{spot_fleet.title}",
        template=template,
        PolicyName=Sub(f"${{{spot_fleet.title}}}CpuAverageScaleOut"),
        PolicyType="StepScaling",
        ScalingTargetId=Ref(target),
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType="ChangeInCapacity",
            Cooldown=300,
            MetricAggregationType="Average",
            StepAdjustments=[
                StepAdjustment(MetricIntervalLowerBound=10, ScalingAdjustment="1")
            ],
        ),
    )
    return scale_in_policy, scale_out_policy


def define_default_cw_alarms(template, spot_fleet, scaling_set):
    """
    Function to define CW alarms for the fleet. These default CW Alarms will purely rely on
    EC2 Metrics.

    :param template: Cluster Template
    :type template: troposphere.Template
    :param spot_fleet: The spot fleet the alarms are for
    :type spot_fleet: troposphere.ec2.SpotFleet
    :param scaling_set: Scale In/Out Policies triggered by alarams
    :type scaling_set: tuple

    :returns: void
    """
    Alarm(
        f"LowCpuAverageAlarm{spot_fleet.title}",
        template=template,
        ActionsEnabled=True,
        AlarmActions=[Ref(scaling_set[0])],
        AlarmDescription=Sub(f"LOW CPU USAGE FOR ${{{spot_fleet.title}}}"),
        AlarmName=Sub(f"CPU_AVG_LOW_${{{spot_fleet.title}}}"),
        ComparisonOperator="LessThanOrEqualToThreshold",
        Dimensions=[CwMetricDimension(Name="FleetRequestId", Value=Ref(spot_fleet))],
        EvaluationPeriods=5,
        Period=60,
        Namespace="AWS/EC2Spot",
        MetricName="CPUUtilization",
        Statistic="Average",
        Threshold="25",
        Unit="Percent",
        TreatMissingData="notBreaching",
    )

    Alarm(
        f"HighCpuAverageAlarm{spot_fleet.title}",
        ActionsEnabled=True,
        AlarmActions=[Ref(scaling_set[1])],
        AlarmDescription=Sub(f"LOW CPU USAGE FOR ${{{spot_fleet.title}}}"),
        AlarmName=Sub(f"CPU_AVG_HIGH_${{{spot_fleet.title}}}"),
        ComparisonOperator="GreaterThanOrEqualToThreshold",
        Dimensions=[CwMetricDimension(Name="FleetRequestId", Value=Ref(spot_fleet))],
        EvaluationPeriods=5,
        Period=60,
        Namespace="AWS/EC2Spot",
        MetricName="CPUUtilization",
        Statistic="Average",
        Threshold="65",
        Unit="Percent",
        TreatMissingData="notBreaching",
    )


def define_spot_fleet(template, settings, lt_id, lt_version, spot_config):
    """
    Function to add a spot fleet to the cluster template

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for execution
    :param template: Source template
    :type template: troposphere.Template

    :returns: NIL
    """
    configs = define_overrides(settings, lt_id, lt_version, spot_config)
    role = add_fleet_role(template)
    fleet = SpotFleet(
        "EcsClusterFleet",
        template=template,
        SpotFleetRequestConfigData=SpotFleetRequestConfigData(
            AllocationStrategy="diversified",
            ExcessCapacityTerminationPolicy="default",
            IamFleetRole=GetAtt(role, "Arn"),
            InstanceInterruptionBehavior="terminate",
            TargetCapacity=Ref(compute_params.TARGET_CAPACITY),
            Type="maintain",
            SpotPrice=str(spot_config["bid_price"]),
            ReplaceUnhealthyInstances=True,
            LaunchTemplateConfigs=configs,
        ),
    )
    scaling_set = add_scaling_policies(template, fleet, role)
    define_default_cw_alarms(template, fleet, scaling_set)


def generate_spot_fleet_template(settings, spot_config):
    """
    Generates a standalone template for SpotFleet
    """
    template = build_template(
        "Template For SpotFleet As Part Of EcsCluster",
        [
            compute_params.LAUNCH_TEMPLATE_ID,
            compute_params.LAUNCH_TEMPLATE_VersionNumber,
            compute_params.MIN_CAPACITY,
            compute_params.MAX_CAPACITY,
            compute_params.TARGET_CAPACITY,
            vpc_params.APP_SUBNETS,
        ],
    )
    template.add_condition(
        compute_conditions.MAX_IS_MIN_T, compute_conditions.MAX_IS_MIN
    )
    lt_id = Ref(compute_params.LAUNCH_TEMPLATE_ID)
    lt_version = Ref(compute_params.LAUNCH_TEMPLATE_VersionNumber)
    define_spot_fleet(template, settings, lt_id, lt_version, spot_config)
    return template
