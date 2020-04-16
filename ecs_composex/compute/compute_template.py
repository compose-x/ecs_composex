# -*- coding: utf-8 -*-

"""
Main module generating the ECS Cluster template.

The root stack is to build the IAM Instance profile for the hosts that can be used for ASG or SpotFleet.
That way it is easy for anyone to deploy an instance in standalone if you wanted that.
"""

from troposphere import Ref, If, GetAtt
from troposphere.cloudformation import Stack
from ecs_composex.compute import compute_params, compute_conditions
from ecs_composex.compute.hosts_template import add_hosts_resources
from ecs_composex.compute.spot_fleet import (
    generate_spot_fleet_template,
    DEFAULT_SPOT_CONFIG,
)
from ecs_composex.common import (
    build_template,
    KEYISSET,
    LOG,
    add_parameters,
    write_template_to_file,
)
from ecs_composex.common import cfn_conditions
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME,
    ROOT_STACK_NAME_T,
    USE_FLEET,
    USE_ONDEMAND,
)
from ecs_composex.common.templates import upload_template
from ecs_composex.vpc import vpc_params
from ecs_composex.ecs.ecs_params import CLUSTER_NAME
from ecs_composex.common.tagging import add_object_tags


def add_spotfleet_stack(
    template, region_azs, compose_content, launch_template, tags=None, **kwargs
):
    """
    Function to build the spotfleet stack and add it to the Cluster parent template

    :param launch_template: the launch template
    :type launch_template: troposphere.ec2.LaunchTemplate
    :param template: parent cluster template
    :type template: troposphere.Template
    :param compose_content: docker / composeX file content
    :type compose_content: dict
    :param region_azs: List of AWS Azs i.e. ['eu-west-1a', 'eu-west-1b']
    :type region_azs: list
    :param tags: tuple of tags to add to objects and the template
    :type tags: tuple
    """
    spot_config = None
    parameters = {
        ROOT_STACK_NAME_T: If(
            cfn_conditions.USE_STACK_NAME_CON_T,
            Ref("AWS::StackName"),
            Ref(ROOT_STACK_NAME),
        ),
        compute_params.LAUNCH_TEMPLATE_ID_T: Ref(launch_template),
        compute_params.LAUNCH_TEMPLATE_VersionNumber_T: GetAtt(
            launch_template, "LatestVersionNumber"
        ),
        compute_params.MAX_CAPACITY_T: Ref(compute_params.MAX_CAPACITY),
        compute_params.MIN_CAPACITY_T: Ref(compute_params.MIN_CAPACITY),
        compute_params.TARGET_CAPACITY_T: Ref(compute_params.TARGET_CAPACITY),
    }
    if KEYISSET("configs", compose_content):
        configs = compose_content["configs"]
        if KEYISSET("spot_config", configs):
            spot_config = configs["spot_config"]

    if spot_config:
        kwargs.update({"spot_config": spot_config})
    else:
        LOG.warn("No spot_config set in configs of ComposeX File. Setting to defaults")
        kwargs.update({"spot_config": DEFAULT_SPOT_CONFIG})
    fleet_template = generate_spot_fleet_template(region_azs, **kwargs)
    if tags and tags[0]:
        add_parameters(fleet_template, tags[0])
        for tag in tags[0]:
            parameters.update({tag.title: Ref(tag.title)})
        for resource in fleet_template.resources:
            add_object_tags(fleet_template.resources[resource], tags[1])
    fleet_template_url = upload_template(
        fleet_template.to_json(), kwargs["BucketName"], "spot_fleet.json"
    )
    if not fleet_template_url:
        LOG.warn(
            "Fleet template URL not returned. Not adding SpotFleet to Cluster stack"
        )
        return
    write_template_to_file(fleet_template, "/tmp/spot_fleet.yml")
    template.add_resource(
        Stack(
            "SpotFleet",
            Condition=cfn_conditions.USE_SPOT_CON_T,
            TemplateURL=fleet_template_url,
            Parameters=parameters,
        )
    )


def generate_compute_template(region_azs, compose_content=None, tags=None, **kwargs):
    """
    Function that generates the Compute resources to run ECS services on top of EC2

    :param tags: tuple tags to add to the template as parameters and to objects as Tags
    :type tags: tuple
    :param region_azs: List of AZs for hosts, i.e. ['eu-west-1', 'eu-west-b']
    :type region_azs: list
    :param compose_content: Compose dictionary to parse for services etc.
    :type compose_content: dict

    :return: ECS Cluster Template
    :rtype: troposphere.Template
    """
    if tags is None:
        tags = ()
    template = build_template(
        "Cluster template generated by ECS Compose X",
        [
            USE_FLEET,
            USE_ONDEMAND,
            compute_params.ECS_AMI_ID,
            compute_params.TARGET_CAPACITY,
            compute_params.MIN_CAPACITY,
            compute_params.MAX_CAPACITY,
            vpc_params.APP_SUBNETS,
            vpc_params.VPC_ID,
            CLUSTER_NAME,
        ],
    )
    if tags and tags[0]:
        LOG.info("adding tags")
        add_parameters(template, tags[0])
    template.add_condition(
        compute_conditions.MAX_IS_MIN_T, compute_conditions.MAX_IS_MIN
    )
    template.add_condition(cfn_conditions.USE_SPOT_CON_T, cfn_conditions.USE_SPOT_CON)
    launch_template = add_hosts_resources(template)
    add_spotfleet_stack(
        template, region_azs, compose_content, launch_template, tags, **kwargs
    )
    if tags and tags[1]:
        for resource in template.resources:
            add_object_tags(template.resources[resource], tags[1])
    return template
