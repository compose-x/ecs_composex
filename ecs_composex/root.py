# -*- coding: utf-8 -*-
"""Module to generate a full stack with VPC & Cluster."""

import boto3
from troposphere import Ref, GetAtt, If, Join
from troposphere.cloudformation import Stack
from troposphere.ecs import Cluster

from ecs_composex import XFILE_DEST
from ecs_composex.common import (
    LOG, add_parameters, validate_kwargs, build_parameters_file,
    build_default_stack_parameters
)
from ecs_composex.common import (
    build_template, KEYISSET,
    load_composex_file
)
from ecs_composex.common.cfn_params import (
    ROOT_STACK_NAME_T,
    USE_FLEET, USE_FLEET_T,
    USE_ONDEMAND, USE_ONDEMAND_T
)
from ecs_composex.common.tagging import generate_tags_parameters, add_object_tags
from ecs_composex.common.templates import upload_template
from ecs_composex.compute import create_compute_stack
from ecs_composex.compute.compute_params import (
    TARGET_CAPACITY_T,
    TARGET_CAPACITY,
    MIN_CAPACITY_T
)
from ecs_composex.ecs import ecs_params, create_services_templates
from ecs_composex.ecs.ecs_conditions import (
    GENERATED_CLUSTER_NAME_CON_T,
    GENERATED_CLUSTER_NAME_CON,
    CLUSTER_NAME_CON_T,
    CLUSTER_NAME_CON
)
from ecs_composex.ecs.ecs_params import CLUSTER_NAME_T, CLUSTER_NAME
from ecs_composex.ecs_composex import (
    RES_REGX, get_mod_function
)
from ecs_composex.vpc import create_vpc_template
from ecs_composex.vpc import vpc_params

ROOT_CLUSTER_NAME = 'EcsCluster'

VPC_ARGS = [
    vpc_params.PUBLIC_SUBNETS_T,
    vpc_params.APP_SUBNETS_T,
    vpc_params.STORAGE_SUBNETS_T,
    vpc_params.VPC_ID_T, vpc_params.VPC_MAP_ID_T
]


def generate_vpc_parameters(template, params, **kwargs):
    """
    Function to add the VPC arguments to the root stack

    :param template: the root template to add the parameters to
    :type template: troposphere.Template
    :param params: list of parameters
    :type params: list
    """
    for arg in VPC_ARGS:
        if KEYISSET(arg, kwargs):
            build_parameters_file(
                params, arg, kwargs[arg]
            )
    params = [
        vpc_params.VPC_ID,
        vpc_params.APP_SUBNETS,
        vpc_params.STORAGE_SUBNETS,
        vpc_params.PUBLIC_SUBNETS,
        vpc_params.VPC_MAP_ID
    ]
    add_parameters(template, params)


def add_vpc_to_root(root_template, session, tags_params=None, **kwargs):
    """
    Function to add VPC stack to the root one.

    :param tags_params: Tags to add to the stack
    :param root_template: root stack template
    :type root_template: troposphere.Template
    :param session: boto session for override
    :type session: boto3.session.Session
    :param kwargs:

    :return: vpc_stack
    :rtype: troposphere.cloudformation.Stack
    """
    if tags_params is None:
        tags_params = ()
    vpc_template = create_vpc_template(
        session=session,
        **kwargs
    )
    vpc_template_url = upload_template(
        vpc_template.to_json(),
        kwargs['BucketName'],
        'vpc.json',
        session=session
    )
    LOG.debug(vpc_template_url)
    with open(f"{kwargs['output_file']}.vpc.json", 'w') as vpc_fd:
        vpc_fd.write(vpc_template.to_json())
    parameters = {
        ROOT_STACK_NAME_T: Ref('AWS::StackName')
    }
    for param in tags_params:
        parameters.update({param.title: Ref(param.title)})
    vpc_stack = root_template.add_resource(
        Stack(
            'Vpc',
            TemplateURL=vpc_template_url,
            Parameters=parameters
        )
    )
    return vpc_stack


def add_compute(root_template, dependencies, params, vpc_stack=None, tags=None, session=None, **kwargs):
    """
    Function to add Cluster stack to root one. If any of the options related to compute resources are set in the CLI
    then this function will generate and add the compute template to the root stack template

    :param dependencies: list of dependencies that need created before creating the Compute stack
    :type dependencies: list
    :param root_template: the root template
    :type root_template: troposphere.Template
    :param params: list of parameters
    :param vpc_stack: the VPC stack if any to pull the attributes from
    :param session: override boto3 session
    :param tags: tags to add to the stack
    :type tags: tuple

    :return: compute_stack, the Compute stack
    :rtype: troposphere.cloudformation.Stack
    """
    create_compute = False
    args = [USE_FLEET_T, USE_ONDEMAND_T, "AddComputeResources"]
    for arg in args:
        if KEYISSET(arg, kwargs):
            create_compute = True
    if not create_compute:
        return
    if params is None:
        params = []
    if tags is None:
        tags = ()
    depends_on = []
    root_template.add_parameter(TARGET_CAPACITY)
    compute_template = create_compute_stack(session, **kwargs)
    parameters = {
        ROOT_STACK_NAME_T: Ref('AWS::StackName'),
        TARGET_CAPACITY_T: Ref(TARGET_CAPACITY),
        MIN_CAPACITY_T: Ref(TARGET_CAPACITY),
        USE_FLEET_T: Ref(USE_FLEET),
        USE_ONDEMAND_T: Ref(USE_ONDEMAND)
    }
    for tag in tags[0]:
        parameters.update({tag.title: Ref(tag.title)})
    if vpc_stack is not None:
        depends_on.append(vpc_stack)
        parameters.update({
            vpc_params.VPC_ID_T: GetAtt(vpc_stack, f"Outputs.{vpc_params.VPC_ID_T}"),
            vpc_params.APP_SUBNETS_T: GetAtt(vpc_stack, f"Outputs.{vpc_params.APP_SUBNETS_T}"),
        })
    else:
        # Setup parameters for compute stack without VPC pre-created
        if not kwargs[vpc_params.APP_SUBNETS_T]:
            raise ValueError("No application subnets were provided to create the compute")
        if params is None:
            raise TypeError("params is ", params, "expected", list)
        root_template.add_parameter(vpc_params.APP_SUBNETS)
        parameters.update({
            vpc_params.APP_SUBNETS_T: Ref(vpc_params.APP_SUBNETS)
        })
        build_parameters_file(params, vpc_params.APP_SUBNETS_T, kwargs[vpc_params.APP_SUBNETS_T])

    compute_stack = root_template.add_resource(Stack(
        'Compute',
        TemplateURL=upload_template(
            template_body=compute_template[0].to_json(),
            bucket_name=kwargs['BucketName'],
            file_name='compute.json',
            session=session,
        ),
        Parameters=parameters,
        DependsOn=dependencies
    ))
    dependencies.append('Compute')
    return compute_stack


def add_x_resources(template, session, tags=None, **kwargs):
    """
    Function to add each X resource from the compose file
    """
    content = load_composex_file(kwargs[XFILE_DEST])
    depends_on = []
    ignore_x = ['x-rds', 'x-tags']
    if tags is None:
        tags = []
    for key in content:
        if key.startswith('x-') and key not in ignore_x:
            res_type = RES_REGX.sub('', key)
            function_name = f"create_{res_type}_template"
            create_function = get_mod_function(res_type, function_name)
            if create_function:
                x_template = create_function(session=session, **kwargs)
                x_template_url = upload_template(
                    x_template.to_json(),
                    kwargs['BucketName'],
                    f"{res_type}.json",
                    session=session
                )
                depends_on.append(res_type.title().strip())
                parameters = {
                    ROOT_STACK_NAME_T: Ref('AWS::StackName')
                }
                for tag in tags:
                    parameters.update({tag.title: Ref(tag.title)})
                template.add_resource(Stack(
                    res_type.title().strip(),
                    TemplateURL=x_template_url,
                    Parameters=parameters
                ))
    return depends_on


def add_services(template, depends, session, vpc_stack=None, **kwargs):
    """
    Function to add the microservices root stack
    :param template: root template
    :type template: troposphere.Template
    :param depends: list of dependencies for the stack
    :type depends: list
    :param session: ovveride boto session for API calls
    :type session: boto3.session.Session
    :param vpc_stack: the VPC Stack
    :type vpc_stack: troposphere.cloudformation.Template
    :param kwargs: optional parameters
    """
    services_template = create_services_templates(session=session, **kwargs)
    services_template_url = upload_template(
        template_body=services_template.to_json(),
        bucket_name=kwargs['BucketName'],
        file_name='services.json'
    )
    parameters = {
        ROOT_STACK_NAME_T: Ref('AWS::StackName')
    }
    if not KEYISSET(CLUSTER_NAME_T, kwargs):
        parameters[ecs_params.CLUSTER_NAME_T] = Ref(ROOT_CLUSTER_NAME)
    else:
        parameters[ecs_params.CLUSTER_NAME_T] = Ref(CLUSTER_NAME)
    if vpc_stack:
        parameters.update({
            vpc_params.VPC_ID_T: GetAtt(vpc_stack, f'Outputs.{vpc_params.VPC_ID_T}'),
            vpc_params.PUBLIC_SUBNETS_T: GetAtt(vpc_stack, f'Outputs.{vpc_params.PUBLIC_SUBNETS_T}'),
            vpc_params.APP_SUBNETS_T: GetAtt(vpc_stack, f'Outputs.{vpc_params.APP_SUBNETS_T}'),
        })
    else:
        parameters.update({
            vpc_params.VPC_ID_T: Ref(vpc_params.VPC_ID),
            vpc_params.PUBLIC_SUBNETS_T: Join(',', Ref(vpc_params.PUBLIC_SUBNETS)),
            vpc_params.APP_SUBNETS_T: Join(',', Ref(vpc_params.APP_SUBNETS)),
        })
    return Stack(
        'Services',
        template=template,
        TemplateURL=services_template_url,
        Parameters=parameters,
        DependsOn=depends
    )


def add_ecs_cluster(template, depends_on=None):
    """
    Function to add the cluster to the root template.

    :param depends_on: list of dependencies for the object
    :type depends_on: list
    :param template: the root stack template
    :type template: troposphere.Template
    """
    template.add_condition(GENERATED_CLUSTER_NAME_CON_T, GENERATED_CLUSTER_NAME_CON)
    template.add_condition(CLUSTER_NAME_CON_T, CLUSTER_NAME_CON)
    if depends_on is None:
        depends_on = []
    Cluster(
        ROOT_CLUSTER_NAME,
        template=template,
        ClusterName=If(
            CLUSTER_NAME_CON_T,
            Ref('AWS::StackName'),
            Ref(CLUSTER_NAME_T)
        ),
        DependsOn=depends_on
    )


def init_root_template(stack_params, tags=None):
    """
    Function to initialize the root template

    :param stack_params: stack parameters
    :type stack_params: list
    :param tags: tags and parameters to add to the template
    :type tags: tuple

    :return: template
    :rtype: troposphere.Template
    """

    template = build_template(
        'Root template generated via ECS ComposeX',
        [USE_FLEET, USE_ONDEMAND, CLUSTER_NAME]
    )
    if tags and tags[0] and isinstance(tags[0], list):
        add_parameters(template, tags[0])
        for param in tags[0]:
            build_parameters_file(stack_params, param.title, param.Default)
    return template


def generate_full_template(session=None, **kwargs):
    """
    Function to generate the root template

    :param session: boto3 session to override client
    :type session: boto3.session.Session

    :return template: Template()
    """
    if session is None:
        session = boto3.session.Session(region_name=kwargs['AwsRegion'])
    stack_params = []
    build_default_stack_parameters(stack_params, **kwargs)
    tags_params = generate_tags_parameters(load_composex_file(kwargs[XFILE_DEST]))
    template = init_root_template(stack_params, tags_params)
    LOG.debug(kwargs)
    validate_kwargs(['BucketName'], kwargs)
    vpc_stack = None
    depends_on = add_x_resources(template, session=session, **kwargs)
    if KEYISSET('CreateVpc', kwargs):
        vpc_stack = add_vpc_to_root(template, session, tags_params[0], **kwargs)
        depends_on.append(vpc_stack)
        add_object_tags(vpc_stack, tags_params[1])
    else:
        generate_vpc_parameters(template, stack_params, **kwargs)
        LOG.debug(stack_params)
    if KEYISSET(CLUSTER_NAME_T, kwargs):
        build_parameters_file(stack_params, CLUSTER_NAME_T, kwargs[CLUSTER_NAME_T])
    if KEYISSET('CreateCluster', kwargs):
        add_ecs_cluster(template, depends_on)
        depends_on.append(ROOT_CLUSTER_NAME)
    add_compute(template, depends_on, stack_params, vpc_stack, tags=tags_params, session=session, **kwargs)
    add_services(template, depends_on, session=session, vpc_stack=vpc_stack, **kwargs)

    for resource in template.resources:
        add_object_tags(template.resources[resource], tags_params[1])
    return template, stack_params
