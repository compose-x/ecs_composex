#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
Module to create the Launch Template for the hosts and the associated security group and
IAM Role (with Instance Profile).

The Launch Template uses CFN-INIT in order to bootstrap the machine at runtime, avoiding
any hardcoding, especially not for the ECS Service

These settings are all documented on AWS official documentation:
https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-agent-config.html
"""

from troposphere import Base64, GetAtt, Join, Ref, Sub, Tags, cloudformation
from troposphere.ec2 import (
    EBSBlockDevice,
    IamInstanceProfile,
    LaunchTemplate,
    LaunchTemplateBlockDeviceMapping,
    LaunchTemplateData,
    Monitoring,
    SecurityGroup,
    TagSpecifications,
)
from troposphere.iam import InstanceProfile, Policy, Role

from ecs_composex.compute import compute_params
from ecs_composex.compute.compute_params import HOST_PROFILE_T, HOST_ROLE_T, NODES_SG_T
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.vpc import vpc_params


def add_hosts_profile(template):
    """
    Adds role to the template

    :parm template: EC2 Cluster template to add the role and profile to
    :type template: troposphere.Template

    :returns: troposphere IAM Role for EC2 hosts
    :rtype: troposphere.iam.Role
    """
    ecs_policy = Policy(
        PolicyName="AllowEcsSpecific",
        PolicyDocument={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecs:RegisterContainerInstance",
                        "ecs:UpdateContainerInstancesState",
                        "ecs:DeregisterContainerInstance",
                    ],
                    "Resource": [
                        Sub(
                            "arn:${AWS::Partition}:ecs:${AWS::Region}:${AWS::AccountId}:"
                            f"cluster/${{{CLUSTER_NAME_T}}}"
                        )
                    ],
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ecs:StartTelemetrySession",
                        "ecs:DiscoverPollEndpoint",
                        "ecs:Submit*",
                        "ecs:Poll",
                    ],
                    "Resource": ["*"],
                },
            ],
        },
    )
    role = Role(
        HOST_ROLE_T,
        template=template,
        AssumeRolePolicyDocument=service_role_trust_policy("ec2"),
        ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM"],
        Policies=[ecs_policy],
    )
    InstanceProfile(
        HOST_PROFILE_T,
        template=template,
        Roles=[Ref(role)],
    )
    return role


def add_hosts_security_group(template):
    """
    Function to add a security group for the host

    :parm template: EC2 Cluster template to add the SG to
    :type template: troposphere.Template

    :returns: troposphere IAM Role for EC2 hosts
    :rtype: troposphere.ec2.SecurityGroup
    """
    return SecurityGroup(
        NODES_SG_T,
        template=template,
        GroupDescription=Sub(f"Group for hosts in ${{{CLUSTER_NAME_T}}}"),
        VpcId=Ref(vpc_params.VPC_ID),
    )


def add_launch_template(template, hosts_sg):
    """Function to create a launch template.

    :param template: ECS Cluster template
    :type template: troposphere.Template
    :param hosts_sg: security group for the EC2 hosts
    :type hosts_sg: troposphere.ec2.SecurityGroup

    :return: launch_template
    :rtype: troposphere.ec2.LaunchTemplate
    """

    launch_template = LaunchTemplate(
        "LaunchTemplate",
        template=template,
        Metadata=cloudformation.Metadata(
            cloudformation.Init(
                cloudformation.InitConfigSets(
                    default=["awspackages", "dockerconfig", "ecsconfig", "awsservices"]
                ),
                awspackages=cloudformation.InitConfig(
                    packages={"yum": {"awslogs": [], "amazon-ssm-agent": []}},
                    commands={
                        "001-check-packages": {"command": "rpm -qa | grep amazon"},
                        "002-check-packages": {"command": "rpm -qa | grep aws"},
                    },
                ),
                awsservices=cloudformation.InitConfig(
                    services={
                        "sysvinit": {
                            "amazon-ssm-agent": {"enabled": True, "ensureRunning": True}
                        }
                    }
                ),
                dockerconfig=cloudformation.InitConfig(
                    commands={
                        "001-stop-docker": {"command": "systemctl stop docker"},
                        "098-reload-systemd": {"command": "systemctl daemon-reload"},
                    },
                    files={
                        "/etc/sysconfig/docker": {
                            "owner": "root",
                            "group": "root",
                            "mode": "644",
                            "content": Join(
                                "\n",
                                [
                                    "DAEMON_MAXFILES=1048576",
                                    Join(
                                        " ",
                                        ["OPTIONS=--default-ulimit nofile=1024:4096"],
                                    ),
                                    "DAEMON_PIDFILE_TIMEOUT=10",
                                    "#EOF",
                                    "",
                                ],
                            ),
                        }
                    },
                    services={
                        "sysvinit": {
                            "docker": {
                                "enabled": True,
                                "ensureRunning": True,
                                "files": ["/etc/sysconfig/docker"],
                                "commands": ["098-reload-systemd"],
                            }
                        }
                    },
                ),
                ecsconfig=cloudformation.InitConfig(
                    files={
                        "/etc/ecs/ecs.config": {
                            "owner": "root",
                            "group": "root",
                            "mode": "644",
                            "content": Join(
                                "\n",
                                [
                                    Sub(f"ECS_CLUSTER=${{{CLUSTER_NAME_T}}}"),
                                    "ECS_ENABLE_TASK_IAM_ROLE=true",
                                    "ECS_ENABLE_SPOT_INSTANCE_DRAINING=true",
                                    "ECS_ENABLE_TASK_IAM_ROLE_NETWORK_HOST=true",
                                    "ECS_ENABLE_CONTAINER_METADATA=true",
                                    "ECS_ENABLE_UNTRACKED_IMAGE_CLEANUP=true",
                                    "ECS_UPDATES_ENABLED=true",
                                    "ECS_ENGINE_TASK_CLEANUP_WAIT_DURATION=15m",
                                    "ECS_IMAGE_CLEANUP_INTERVAL=10m",
                                    "ECS_NUM_IMAGES_DELETE_PER_CYCLE=100",
                                    "ECS_ENABLE_TASK_ENI=true",
                                    "ECS_AWSVPC_BLOCK_IMDS=true",
                                    "ECS_TASK_METADATA_RPS_LIMIT=300,400",
                                    "ECS_ENABLE_AWSLOGS_EXECUTIONROLE_OVERRIDE=true",
                                    'ECS_AVAILABLE_LOGGING_DRIVERS=["awslogs", "json-file"]',
                                    "#EOF",
                                ],
                            ),
                        }
                    },
                    commands={
                        "0001-restartecs": {
                            "command": "systemctl --no-block restart ecs"
                        }
                    },
                ),
            )
        ),
        LaunchTemplateData=LaunchTemplateData(
            BlockDeviceMappings=[
                LaunchTemplateBlockDeviceMapping(
                    DeviceName="/dev/xvda",
                    Ebs=EBSBlockDevice(DeleteOnTermination=True, Encrypted=True),
                )
            ],
            ImageId=Ref(compute_params.ECS_AMI_ID),
            InstanceInitiatedShutdownBehavior="terminate",
            IamInstanceProfile=IamInstanceProfile(
                Arn=Sub(f"${{{HOST_PROFILE_T}.Arn}}")
            ),
            TagSpecifications=[
                TagSpecifications(
                    ResourceType="instance",
                    Tags=Tags(
                        Name=Sub(f"EcsNodes-${{{CLUSTER_NAME_T}}}"),
                        StackName=Ref("AWS::StackName"),
                        StackId=Ref("AWS::StackId"),
                    ),
                )
            ],
            InstanceType="m5a.large",
            Monitoring=Monitoring(Enabled=True),
            SecurityGroupIds=[GetAtt(hosts_sg, "GroupId")],
            UserData=Base64(
                Join(
                    "\n",
                    [
                        "#!/usr/bin/env bash",
                        "export PATH=$PATH:/opt/aws/bin",
                        "cfn-init -v || yum install aws-cfn-bootstrap -y",
                        Sub(
                            "cfn-init --region ${AWS::Region} -r LaunchTemplate -s ${AWS::StackName}"
                        ),
                        "# EOF",
                    ],
                )
            ),
        ),
        LaunchTemplateName=Ref(CLUSTER_NAME_T),
    )
    return launch_template


def add_hosts_resources(template):
    """Function to add the LaunchTemplate, SG and IAM Profile to go along with the ECS Cluster

    :param template: the ecs_cluster template to add the hosts config to
    :type template: troposphere.Template

    :return: launch_template
    :rtype: troposphere.ec2.LaunchTemplate
    """
    hosts_sg = add_hosts_security_group(template)
    add_hosts_profile(template)
    launch_template = add_launch_template(template, hosts_sg)
    return launch_template
