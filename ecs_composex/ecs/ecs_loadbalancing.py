# -*- coding: utf-8 -*-
"""
Module to generate specific rules and otherwise configurations to allow communication between the
microservices
"""
from troposphere import (
    Ref, Sub, GetAtt, Select, Tags
)
from troposphere.ec2 import (
    EIP, SecurityGroup, SecurityGroupIngress
)
from troposphere.ecs import (
    LoadBalancer as EcsLoadBalancer
)
from troposphere.elasticloadbalancingv2 import (
    LoadBalancer,
    LoadBalancerAttributes,
    TargetGroup, TargetGroupAttribute,
    Listener,
    Action as ListenerAction,
    SubnetMapping
)

from ecs_composex.common import KEYISSET, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.ecs.ecs_networking_ingress import (
    add_lb_to_service_ingress,
    add_public_security_group_ingress
)
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T, SERVICE_NAME, SG_T
)
from ecs_composex.vpc.vpc_params import (
    VPC_ID, PUBLIC_SUBNETS
)


def define_grace_period(template, service):
    """Function to define grace period
    TO IMPLEMENT
    """
    return Ref('AWS::NoValue')


def add_public_ips(template, service_name, azs):
    """Function to add EIPs for each AZ selected for build

    :param template: template of the service to add the resources
    :type template: troposphere.Template
    :param service_name: name of the service
    :type service_name: str
    :param azs: list of AZs to deploy the EIPs to
    :type azs: list

    :return: list of troposphere.ec2.EIP
    :rtype: list
    """
    eips = []
    for az in azs:
        eips.append(
            EIP(
                f"EipPublicNlb{az.replace('-', '').strip()}{service_name}",
                template=template,
                Domain='vpc'
            )
        )
    return eips


def define_public_mapping(eips, azs):
    """Function to get the public mapping for NLB

    :param eips: list of EIPSs
    :type eips: list(troposphere.ec2.EIP)
    :param azs: list of AZs to created EIPs into
    :type azs: list

    :return: list
    """
    public_mappings = []
    if eips:
        public_mappings = [
            SubnetMapping(
                AllocationId=GetAtt(eip, 'AllocationId'),
                SubnetId=Select(count, Ref(PUBLIC_SUBNETS))
            ) for count, eip in enumerate(eips)
        ]
    elif azs:
        public_mappings = [
            SubnetMapping(
                SubnetId=Select(count, Ref(PUBLIC_SUBNETS))
            ) for count in range(len(azs))
        ]
    return public_mappings


def add_alb_sg(template, ports, public):
    """Function to add a security group for application loadbalancer

    :param template: template of the service to add resources to
    :type template: troposphere.Template
    :param ports: list of ports to add ingress from the ALB to service to
    :type ports: list of ports
    :param public: whether the ALB is public
    :type public: int

    :return: The ALB's SG
    :rtype: troposphere.ec2.SecurityGroup
    """
    suffix = 'Private'
    if public:
        suffix = "Public"
    sg = SecurityGroup(
        f"AlbSecurityGroup{suffix}",
        template=template,
        GroupDescription=Sub(f"ALB SG for ${{{SERVICE_NAME_T}}} in ${{{ROOT_STACK_NAME_T}}}"),
        VpcId=Ref(VPC_ID),
        Tags=Tags(
            {
                'Name': Sub(f"alb-sg-${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                'StackName': Ref('AWS::StackName'),
                'MicroserviceName': Ref(SERVICE_NAME)
            }
        )
    )
    for port in ports:
        SecurityGroupIngress(
            f'FromAlbToServiceOnPort{port}',
            template=template,
            FromPort=port,
            ToPort=port,
            GroupId=GetAtt(SG_T, 'GroupId'),
            SourceSecurityGroupId=GetAtt(sg, 'GroupId'),
            SourceSecurityGroupOwnerId=Ref('AWS::AccountId'),
            IpProtocol='tcp'
        )
    return sg


def add_lb_listener(template, port, lb, settings, tgt):
    """Function add listener for the LB

    :param template: template of the service to add resources to
    :type template: troposphere.Template
    :param port: port to add the listener for
    :type port: int
    :param lb: the loadbalancer the listener depends on
    :type lb: tropopshere.elasticloadbalancingv2.LoadBalancer
    :param settings: network settings as defined in :func: ecs_composex.ecs.ecs_networking
    :type settings: dict
    :param tgt: the target group to associate
    :type tgt: troposphere.elasticloadbalancingv2.TargetGroup

    :return: listener
    :rtype: troposphere.elasticloadbalancingv2.Listener
    """
    suffix = 'Private'
    if settings['is_public']:
        suffix = 'Public'
    listener = Listener(
        f"{settings['lb_type'].title()}{suffix}ListenerPort{port}",
        template=template,
        DependsOn=[lb],
        DefaultActions=[
            ListenerAction(
                Type='forward',
                TargetGroupArn=Ref(tgt)
            )
        ],
        LoadBalancerArn=Ref(lb),
        Port=port,
        Protocol='TCP' if settings['lb_type'] == 'network' else 'HTTP'
    )
    return listener


def add_target_group(template, port, lb, settings):
    """Function to generate the TargetGroups

    :param template: the service template to add resources to
    :type template: troposphere.Template
    :param port: the port to add the targetgroup for
    :type port: int
    :param lb: the loadbalancer the targetgroup will be bound to
    :type lb: troposphere.elasticloadbalancingv2.LoadBalancer
    :param settings: network settings as defined in :func: ecs_composex.ecs.ecs_networking
    :type settings: dict

    :return: target group
    :rtype: troposphere.elasticloadbalancingv2.TargetGroup
    """
    suffix = 'Private'
    if settings['is_public']:
        suffix = 'Public'
    tgt = TargetGroup(
        f"{settings['lb_type'].title()}{suffix}TargetGroupPort{port}".strip(),
        template=template,
        DependsOn=[lb],
        VpcId=Ref(VPC_ID),
        Port=port,
        Protocol='TCP' if settings['lb_type'] == 'network' else 'HTTP',
        TargetType='ip',
        HealthCheckIntervalSeconds=10,
        HealthyThresholdCount=2,
        UnhealthyThresholdCount=2,
        TargetGroupAttributes=[
            TargetGroupAttribute(
                Key='deregistration_delay.timeout_seconds',
                Value='10'
            )
        ],
        Tags=Tags(
            {
                'Name': Sub(f"${{{SERVICE_NAME_T}}}-{port}"),
                'StackName': Ref('AWS::StackName'),
                'StackId': Ref('AWS::StackId'),
                'MicroserviceName': Ref(SERVICE_NAME_T)
            }
        )
    )
    return tgt


def add_load_balancer(template, service_name, settings, ports, **kwargs):
    """Function to add LB to template

    :param template: template to add the resources to
    :type template: troposphere.Template
    :param service_name: name of the service
    :type service_name: str
    :param settings: network settings as defined in :func: ecs_composex.ecs.ecs_networking
    :type settings: dict
    :param ports: list of ports to accept ingress for that service
    :type ports: list
    :param kwargs: optional arguments
    :type: dict

    :return: loadbalancer
    :rtype: troposphere.elasticloadbalancingv2.LoadBalancer
    """
    alb_sg = None
    eips = []
    if KEYISSET('is_public', settings) and settings['lb_type'] == 'network':
        eips = add_public_ips(template, service_name, kwargs['AwsAzs'])

    no_value = Ref('AWS::NoValue')
    public_mapping = define_public_mapping(eips, kwargs['AwsAzs'])
    if ports and settings['lb_type'] == 'application':
        alb_sg = add_alb_sg(template, ports, settings['is_public'])
        add_lb_to_service_ingress(template, alb_sg, SG_T, settings)
        lb_sg = [Ref(alb_sg)]
    else:
        lb_sg = no_value

    loadbalancer = LoadBalancer(
        f"Microservice{settings['lb_type'].title()}LB",
        template=template,
        Scheme='internet-facing' if settings['is_public'] else 'internal',
        LoadBalancerAttributes=[
            LoadBalancerAttributes(
                Key='load_balancing.cross_zone.enabled',
                Value='true'
            )
        ] if settings['lb_type'] == 'network' else no_value,
        SecurityGroups=lb_sg,
        SubnetMappings=public_mapping if settings['is_public'] and settings['lb_type'] == 'network' else no_value,
        Subnets=Ref(PUBLIC_SUBNETS) if settings['is_public'] and settings['lb_type'] == 'application' else no_value,
        Type=settings['lb_type'],
        Tags=Tags(
            {
                'Name': Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                'StackName': Ref('AWS::StackName'),
                'MicroserviceName': Ref(SERVICE_NAME)
            }
        )
    )
    if settings['is_public']:
        if settings['lb_type'] == 'application' and alb_sg:
            add_public_security_group_ingress(
                template, service_name, settings, alb_sg
            )
        elif settings['lb_type'] == 'network':
            add_public_security_group_ingress(
                template, service_name, settings, SG_T
            )
    return loadbalancer


def add_service_load_balancer(template, service_name, settings, **kwargs):
    """Function to add all ELBv2 resources for a microservice

    :param template: template to add the resources to
    :type template: troposphere.Template
    :param service_name:
    :type service_name: str
    :param settings:
    :type settings: dict
    :param kwargs:
    :type kwargs: dict

    :return: service_lbs, depends_on
    :rtype: tuple
    """
    service_lbs = []
    tgt_groups = []
    depends_on = []
    curated_ports = [port['target'] for port in settings['ports']]
    service_lb = add_load_balancer(
        template, service_name, settings, curated_ports, **kwargs
    )
    depends_on.append(service_lb.title)
    for port in curated_ports:
        tgt = add_target_group(template, port, service_lb, settings)
        listener = add_lb_listener(template, port, service_lb, settings, tgt)
        tgt_groups.append(tgt)
        depends_on.append(tgt.title)
        depends_on.append(listener.title)

    for target in tgt_groups:
        service_lbs.append(
            EcsLoadBalancer(
                TargetGroupArn=Ref(target),
                ContainerPort=tgt.Port,
                ContainerName=Ref(SERVICE_NAME)
            )
        )
    return service_lbs, depends_on


def define_lb_type(service_name, labels):
    """Function to determine which LB is to be created

    :param service_name: name of the service
    :type service_name: str
    :param labels: labels to use to determine lb_type
    :type labels: dict

    :return: lb_type
    :rtype: str
    """
    lb_type = 'application'
    if KEYISSET('use_nlb', labels) and KEYISSET('use_alb', labels):
        LOG.warn('Both ALB and NLB are enabled for this service. Defaulting to ALB')
    elif KEYISSET('use_nlb', labels) and not KEYISSET('use_alb', labels):
        LOG.debug(f'Creating a NLB for service {service_name}')
        lb_type = 'network'
    elif not KEYISSET('use_nlb', labels) and KEYISSET('use_alb', labels):
        LOG.debug(f'Creating a ALB for service {service_name}')
    else:
        LOG.warn(
            'Neither ALB or NLB were specified but service was flagged as service.'
            'Defaulting to ALB'
        )
    return lb_type


def define_service_load_balancing(template, service_name, settings, **kwargs):
    """Function to add all the resources for when using ALB or NLB

    :param template: Service template to add resources to
    :type template: troposphere.Template
    :param service_name: name of the service
    :param settings: network settings defined in compile_network_settings
    :type settings: dict
    :param kwargs: Optional arguments
    :type kwargs: dict

    :return: service_lb
    :rtype: tuple
    """
    lb_type = define_lb_type(service_name, settings)
    settings.update({
        'lb_type': lb_type
    })
    LOG.debug(f'Adding LB for service {service_name}')
    return add_service_load_balancer(template, service_name, settings, **kwargs)
