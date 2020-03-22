# -*- coding: utf-8 -*-

"""
Functions to add to the Cluster template when people want to use SpotFleet for their ECS Cluster.
"""

from troposphere import (
    Ref, Sub, GetAtt, Select, If, Split
)

from troposphere.ec2 import (
    SpotFleet, SpotFleetRequestConfigData,
    LaunchTemplate,
    LaunchTemplateConfigs,
    LaunchTemplateSpecification,
    LaunchTemplateOverrides
)

from troposphere.applicationautoscaling import (
    ScalableTarget, StepAdjustment,
    StepScalingPolicyConfiguration,
    ScalingPolicy
)

from troposphere.cloudwatch import (
    Alarm,
    MetricDimension as CwMetricDimension
)
from troposphere.iam import Role
from ecs_composex.common import LOG, build_template
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.vpc import vpc_params
from ecs_composex.compute import cluster_params, cluster_conditions


DEFAULT_SPOT_CONFIG = {
    'use_spot': True,
    'bid_price': 0.42,
    'spot_instance_types': {
        'm5a.xlarge': {
            'weight': 3
        },
        'm5a.2xlarge': {
            'weight': 7
        },
        'm5a.4xlarge': {
            'weight': 15
        }
    }
}


def add_fleet_role(template):
    """Function to create the IAM Role for the EC2 Spot Fleet

    :param template: source template to add the resources to
    :type template: troposphere.Template

    :returns: role
    :rtype: troposphere.iam.Role
    """
    role = Role(
        'IamFleetRole',
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy('spotfleet'),
        ManagedPolicyArns=[
            'arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetAutoscaleRole',
            'arn:aws:iam::aws:policy/service-role/AmazonEC2SpotFleetTaggingRole'
        ]
    )
    return role


def define_overrides(region_azs, lt_id, lt_version, spot_config):
    """Function to generate Overrides for the SpotFleet

    """
    if isinstance(lt_id, LaunchTemplate):
        template_id = Ref(lt_id)
        template_version = GetAtt(lt_id, 'LatestVersionNumber')
    elif not isinstance(lt_id, Ref) or not isinstance(lt_version, Ref):
        raise TypeError(
            f"The launch template and/or version are of type", lt_id, lt_version,
            "Expected", LaunchTemplate, "Or", Ref
        )
    else:
        template_id = lt_id
        template_version = lt_version

    overrides = []
    configs = []
    LOG.debug(spot_config)
    for count, az in enumerate(region_azs):
        LOG.debug(az)
        for itype in spot_config['spot_instance_types']:
            overrides.append(
                LaunchTemplateOverrides(
                    SubnetId=Select(count, Split(',', vpc_params.APP_SUBNETS_IMPORT)),
                    WeightedCapacity=spot_config['spot_instance_types'][itype]['weight'],
                    InstanceType=itype
                )
            )
    configs.append(
        LaunchTemplateConfigs(
            LaunchTemplateSpecification=LaunchTemplateSpecification(
                LaunchTemplateId=template_id,
                Version=template_version
            ),
            Overrides=overrides
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
            cluster_conditions.MAX_IS_MIN_T,
            Ref(cluster_params.MIN_CAPACITY),
            Ref(cluster_params.MAX_CAPACITY)
        ),
        MinCapacity=Ref(cluster_params.MIN_CAPACITY),
        ResourceId=Sub(f'spot-fleet-request/${{{spot_fleet.title}}}'),
        RoleARN=GetAtt(role, 'Arn'),
        ServiceNamespace='ec2',
        ScalableDimension='ec2:spot-fleet-request:TargetCapacity'
    )

    scale_in_policy = ScalingPolicy(
        f"FleetScalingIn{spot_fleet.title}",
        template=template,
        PolicyName=Sub(f'${{{spot_fleet.title}}}ScalingIn'),
        PolicyType='StepScaling',
        ScalingTargetId=Ref(target),
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType='ChangeInCapacity',
            Cooldown=300,
            MetricAggregationType='Average',
            StepAdjustments=[
                StepAdjustment(
                    MetricIntervalLowerBound=10,
                    ScalingAdjustment='-1'
                )
            ]
        )
    )

    scale_out_policy = ScalingPolicy(
        f"FleetScalingOut{spot_fleet.title}",
        template=template,
        PolicyName=Sub(f'${{{spot_fleet.title}}}CpuAverageScaleOut'),
        PolicyType='StepScaling',
        ScalingTargetId=Ref(target),
        StepScalingPolicyConfiguration=StepScalingPolicyConfiguration(
            AdjustmentType='ChangeInCapacity',
            Cooldown=300,
            MetricAggregationType='Average',
            StepAdjustments=[
                StepAdjustment(
                    MetricIntervalLowerBound=10,
                    ScalingAdjustment='1'
                )
            ]
        )
    )
    return (scale_in_policy, scale_out_policy)


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
        AlarmActions=[
            Ref(scaling_set[0])
        ],
        AlarmDescription=Sub(f"LOW CPU USAGE FOR ${{{spot_fleet.title}}}"),
        AlarmName=Sub(f'CPU_AVG_LOW_${{{spot_fleet.title}}}'),
        ComparisonOperator='LessThanOrEqualToThreshold',
        Dimensions=[
            CwMetricDimension(
                Name='FleetRequestId',
                Value=Ref(spot_fleet)
            )
        ],
        EvaluationPeriods=5,
        Period=60,
        Namespace='AWS/EC2Spot',
        MetricName='CPUUtilization',
        Statistic='Average',
        Threshold='25',
        Unit='Percent',
        TreatMissingData='notBreaching'
    )

    Alarm(
        f'HighCpuAverageAlarm{spot_fleet.title}',
        ActionsEnabled=True,
        AlarmActions=[
            Ref(scaling_set[1])
        ],
        AlarmDescription=Sub(f"LOW CPU USAGE FOR ${{{spot_fleet.title}}}"),
        AlarmName=Sub(f'CPU_AVG_HIGH_${{{spot_fleet.title}}}'),
        ComparisonOperator='GreaterThanOrEqualToThreshold',
        Dimensions=[
            CwMetricDimension(
                Name='FleetRequestId',
                Value=Ref(spot_fleet)
            )
        ],
        EvaluationPeriods=5,
        Period=60,
        Namespace='AWS/EC2Spot',
        MetricName='CPUUtilization',
        Statistic='Average',
        Threshold='65',
        Unit='Percent',
        TreatMissingData='notBreaching'
    )


def define_spot_fleet(template, region_azs, lt_id, lt_version, **kwargs):
    """
    Function to add a spot fleet to the cluster template

    :param template: Source template
    :type template: troposphere.Template
    :param region_azs: List of AZs to iterate onto, ie ['eu-west-1a', 'eu-west-1b']
    :type region_azs: list

    :returns: NIL
    """
    configs = define_overrides(region_azs, lt_id, lt_version, kwargs['spot_config'])
    role = add_fleet_role(template)
    fleet = SpotFleet(
        f"EcsClusterFleet",
        template=template,
        SpotFleetRequestConfigData=SpotFleetRequestConfigData(
            AllocationStrategy='diversified',
            ExcessCapacityTerminationPolicy='default',
            IamFleetRole=GetAtt(role, 'Arn'),
            InstanceInterruptionBehavior='terminate',
            TargetCapacity=Ref(cluster_params.TARGET_CAPACITY),
            Type='maintain',
            SpotPrice=str(kwargs['spot_config']['bid_price']),
            ReplaceUnhealthyInstances=True,
            LaunchTemplateConfigs=configs,
        )
    )
    scaling_set = add_scaling_policies(template, fleet, role)
    define_default_cw_alarms(template, fleet, scaling_set)


def generate_spot_fleet_template(region_azs, **kwargs):
    """
    Generates a standalone template for SpotFleet
    """
    template = build_template(
        'Template For SpotFleet As Part Of EcsCluster',
        [
            cluster_params.LAUNCH_TEMPLATE_ID,
            cluster_params.LAUNCH_TEMPLATE_VersionNumber,
            cluster_params.MIN_CAPACITY,
            cluster_params.MAX_CAPACITY,
            cluster_params.TARGET_CAPACITY
        ]
    )
    template.add_condition(
        cluster_conditions.MAX_IS_MIN_T,
        cluster_conditions.MAX_IS_MIN
    )
    lt_id = Ref(cluster_params.LAUNCH_TEMPLATE_ID)
    lt_version = Ref(cluster_params.LAUNCH_TEMPLATE_VersionNumber)
    define_spot_fleet(template, region_azs, lt_id, lt_version, **kwargs)
    return template
