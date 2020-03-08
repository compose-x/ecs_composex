# -*- coding: utf-8 -*-
"""
Functions that will add networking elements for the ECS Service as well as generating
the network configuration for the ServiceDefinition
"""

from troposphere import (
    Ref, Sub, GetAtt, Tags
)
from troposphere.ec2 import (
    SecurityGroup
)
from troposphere.ecs import (
    ServiceRegistry
)
from troposphere.servicediscovery import (
    DnsConfig as SdDnsConfig,
    Service as SdService,
    DnsRecord as SdDnsRecord,
    HealthCheckCustomConfig as SdHealthCheckCustomConfig
)

from ecs_composex.common import KEYISSET, LOG
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.ecs.ecs_loadbalancing import define_service_load_balancing
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T, SERVICE_NAME, SG_T
)
from ecs_composex.vpc.vpc_params import (
    NAMESPACE_ID_IMPORT,
    VPC_ID
)


def add_service_default_sg(template):
    """
    Adds a default security group for the microservice.

    :param template: the template to add the SG to.
    :type template: troposphere.Template

    :return: Security group
    :type: troposphere.ec2.SecurityGroup
    """
    sg = SecurityGroup(
        SG_T,
        template=template,
        GroupDescription=Sub(f"SG for ${{{SERVICE_NAME_T}}} - ${{{ROOT_STACK_NAME_T}}}"),
        Tags=Tags(
            {
                'Name': Sub(f"${{{SERVICE_NAME_T}}}-${{{ROOT_STACK_NAME_T}}}"),
                'StackName': Ref('AWS::StackName'),
                'MicroserviceName': Ref(SERVICE_NAME)
            }
        ),
        VpcId=Ref(VPC_ID)
    )
    return sg


def add_service_to_map(template, service_name, service, settings):
    """
    Function to add the service into a cloudmap
    """
    sd_service = SdService(
        'EcsDiscoveryService',
        template=template,
        Description=f'{service_name}',
        NamespaceId=NAMESPACE_ID_IMPORT,
        HealthCheckCustomConfig=SdHealthCheckCustomConfig(
            FailureThreshold=1.0
        ),
        DnsConfig=SdDnsConfig(
            RoutingPolicy='MULTIVALUE',
            NamespaceId=Ref('AWS::NoValue'),
            DnsRecords=[
                SdDnsRecord(
                    TTL='30',
                    Type='A'
                ),
                SdDnsRecord(
                    TTL='30',
                    Type='SRV'
                )
            ]
        ),
        Name=service_name
    )
    registries = []
    for port in service['ports']:
        registry = ServiceRegistry(
            f"ServiceRegistry{port.split(':')[-1]}",
            RegistryArn=GetAtt(sd_service, 'Arn'),
            Port=port.split(':')[-1]
        )
        registries.append(registry)
    return registries


def define_protocol(port_string):
    """Function to define the port protocol. Default to TCP if not specified otherwise

    :param port_string: the port string to parse from the ports list in the compose file
    :type port_string: str

    :return: protocol, ie. udp or tcp
    :rtype: str
    """
    protocols = ['tcp', 'udp']
    protocol = 'tcp'
    if port_string.find('/'):
        protocol_found = port_string.split('/')[-1].strip()
        if protocol_found in protocols:
            return protocol_found
    return protocol


def define_service_ports(service):
    """Function to define common structure to ports

    :param service: the service as defined in compose file
    :type service: dict

    :return: list of ports the service uses formatted according to dict
    :rtype: list
    """
    ports = []
    valid_keys = ['published', 'target', 'protocol', 'mode']
    service_ports = []
    if KEYISSET('ports', service):
        ports = service['ports']
    for port in ports:
        if isinstance(port, str):
            service_ports.append({
                'protocol': define_protocol(port),
                'published': port.split(':')[0],
                'target': port.split(':')[-1].split('/')[0].strip(),
                'mode': 'awsvpc'
            })
        elif isinstance(port, dict):
            if not set(port).issubset(valid_keys):
                raise KeyError(f"Valid keys are", valid_keys, 'got', port.keys())
            port['mode'] = 'awsvpc'
            service_ports.append(port)
    LOG.debug(service_ports)
    return service_ports


def compile_network_settings(compose_content, service, service_name):
    """Function to generate a set of values used for all network related stuff

    :param compose_content: Docker/ComposeX File content
    :type compose_content: dict
    :param service: service definition as imported from Docker/ComposeX File
    :type service_name: dict
    :param service_name: name of the service as defined in Docker/ComposeX File
    :type service_name: str

    :return: settings
    :rtype: dict
    """
    valid_keys = [
        'use_alb', 'use_nlb', 'use_cloudmap', 'is_public', 'healthcheck', 'ext_sources', 'ports'
    ]
    settings = {}
    globals = {
        'use_cloudmap': True,
        'use_nlb': False,
        'use_alb': True,
        'is_public': False
    }
    if KEYISSET('labels', service):
        settings = service['labels']
    if KEYISSET('configs', compose_content):
        if KEYISSET(service_name, compose_content['configs']):
            LOG.warn(
                f"Service {service_name} has defined configs in the configs section."
                "Overriding with values"
            )
            settings = compose_content['configs'][service_name]
    if (KEYISSET('globals', compose_content['configs']) and
            KEYISSET('network', compose_content['configs']['globals']['network'])):
        globals.update(compose_content['configs']['globals']['network'])
    if not set(settings).issubset(valid_keys):
        LOG.error(valid_keys)
        LOG.error(settings)
        raise KeyError('Invalid keys defined in the network section of the service config in configs')
    for key in valid_keys:
        if key not in settings and key != 'ports':
            if key in globals.keys():
                if key == 'use_cloudmap' and not KEYISSET('is_public', settings):
                    LOG.debug(f'Missing use_cloudmap but {service_name} is public.')
                    settings[key] = False
                else:
                    settings[key] = globals[key]
    settings['ports'] = define_service_ports(service)
    return settings


def define_service_network_config(template, service_name, network_settings, **kwargs):
    """Function to define microservice ingress.

    :param template: service template to add resources to
    :type template: troposphere.Template
    :param service_name: name of the service as defined in the compose file
    :type service_name: str
    :param network_settings: see :func:`ecs_composex.ecs.ecs_networking.compile_network_settings`
    :type network_settings: dict
    :param kwargs: Optional additional parameters

    :return: tuple of the args for the Service() and the dependencies
    :rtype: tuple
    """
    add_service_default_sg(template)
    service_lbs = Ref('AWS::NoValue')
    registries = Ref('AWS::NoValue')
    service_attrs = {
        'LoadBalancers': service_lbs,
        'ServiceRegistries': registries
    }
    external_dependencies = []
    if not KEYISSET('AwsAzs', kwargs):
        raise KeyError(
            'Missing AwsAzs from options.'
            'AZs are required to configure services networking'
        )
    if not KEYISSET('ports', network_settings):
        LOG.debug(f"{service_name} does not have any ports. No ingress necessary")
        return service_attrs, external_dependencies
    LOG.debug(network_settings)
    if KEYISSET('use_nlb', network_settings) or KEYISSET('use_alb', network_settings):
        service_lb = define_service_load_balancing(template, service_name, network_settings, **kwargs)
        service_attrs['LoadBalancers'] = service_lb[0]
        service_attrs['DependsOn'] = service_lb[-1] if isinstance(service_lb[-1], list) else []
    return service_attrs, external_dependencies
