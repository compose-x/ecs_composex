# -*- coding: utf-8 -*-
"""
Module to generate specific rules and otherwise configurations to allow communication between the
microservices
"""
import re

from troposphere import (
    Ref, Sub, GetAtt
)
from troposphere.ec2 import (
    SecurityGroupIngress
)

from ecs_composex.common import KEYISSET, LOG
from ecs_composex.ecs.ecs_params import (
    SERVICE_NAME_T, get_import_service_group_id,
    SG_T, RES_KEY
)

CIDR_REG = r"""((((((([0-9]{1}\.))|([0-9]{2}\.)|
(1[0-9]{2}\.)|(2[0-5]{2}\.)))){3})(((((([0-9]{1}))|
([0-9]{2})|(1[0-9]{2})|(2[0-5]{2}))))){1,3})\/(([0-9])|([1-2][0-9])|((3[0-2])))$"""
CIDR_PAT = re.compile(CIDR_REG)


def flatten_ip(ip_str):
    """Function to remove all non alphanum characters from IP CIDR notation

    :param ip_str:

    :rtype: str
    """
    return ip_str.replace('.', '').split('/')[0].strip()


def add_lb_to_service_ingress(template, lb_sg, service_sg, settings):
    """Function to add Service ingress between the LB and the microservice

    :param template: microservice template
    :param lb_sg:
    :type lb_sg: troposphere.ec2.SecurityGroup
    :param service_sg: security group of the microservice
    :type service_sg: str or troposphere.ec2.SecurityGroup
    :param settings: network settings as defined in compile_network_settings
    :type settings: dict
    """
    LOG.debug(f"Adding ALB ingress to service")
    for port in settings['ports']:
        SecurityGroupIngress(
            f"From{settings['lb_type'].title()}ToServicePort{port['target']}",
            template=template,
            FromPort=port['target'],
            ToPort=port['target'],
            IpProtocol=port['protocol'],
            GroupId=GetAtt(service_sg, 'GroupId'),
            SourceSecurityGroupOwnerId=Ref('AWS::AccountId'),
            SourceSecurityGroupId=GetAtt(lb_sg, 'GroupId'),
            Description=Sub(f"From LB to ${{{SERVICE_NAME_T}}} on port {port['target']}")
        )


def add_public_security_group_ingress(template, service_name, settings, security_group):
    """Function to add public ingress. If a list of IPs is found in the config['ext_sources']
    then it will use that, if not, allows from 0.0.0.0/0

    :param template: service template to add the ingress rules to
    :type template: troposphere.Template
    :param service_name: name of the service
    :type service_name: str
    :param settings: network settings as defined in compile_network_settings
    :type settings: dict
    :param security_group: security group (object or title string) to add the rules to
    :type security_group: str or troposphere.ec2.SecurityGroup
    """
    if KEYISSET('ext_sources', settings) and isinstance(settings['ext_sources'], list):
        allowed_sources = settings['ext_sources']
    else:
        allowed_sources = [{'ipv4': '0.0.0.0/0', 'protocol': -1, 'source_name': 'ANY'}]

    for allowed_source in allowed_sources:
        props = {}
        if not KEYISSET('ipv4', allowed_source) and not KEYISSET('ipv6', allowed_source):
            LOG.warn('No IPv4 or IPv6 set. Skipping')
            continue

        props['CidrIp'] = allowed_source['ipv4'] if KEYISSET('ipv4', allowed_source) else Ref('AWS::NoValue')
        props['CidrIpv6'] = allowed_source['ipv6'] if KEYISSET('ipv6', allowed_source) else Ref('AWS::NoValue')

        if KEYISSET('CidrIp', props) and isinstance(props['CidrIp'], str) and not CIDR_PAT.match(props['CidrIp']):
            LOG.error(f"Falty IP Address: {allowed_source} - service {service_name}")
            raise ValueError('Not a valid IPv4 CIDR notation', props['CidrIp'], 'Expected', CIDR_REG)

        LOG.debug(f"Adding {allowed_source} for ingress")

        for port in settings['ports']:
            if KEYISSET('source_name', allowed_source):
                title = f"From{allowed_source['source_name'].title()}Onto{port['target']}{port['protocol']}"
                description = Sub(
                    f"From {allowed_source['source_name'].title()} "
                    f"To {port['target']}{port['protocol']} for ${{{SERVICE_NAME_T}}}"
                )
            else:
                title = f"From{flatten_ip(allowed_source['ipv4'])}" \
                        "To{port['target']}{port['protocol']}"
                description = Sub(
                    f"Public {port['target']}{port['protocol']}"
                    f" for ${{{SERVICE_NAME_T}}}"
                )
            SecurityGroupIngress(
                title,
                template=template,
                Description=description,
                GroupId=GetAtt(security_group, 'GroupId'),
                IpProtocol=port['protocol'],
                FromPort=port['target'],
                ToPort=port['target'],
                **props
            )


def define_service_to_service_ingress(compose_content, template, service_name, service):
    """
    Function to determine the security group openings from a service to another

    :param compose_content: docker compose dictionary
    :type compose_content: dict
    :param template: the service template to add the resources to
    :type template: troposphere.Template
    :param service_name: name of the service as defined in Docker ComposeX file
    :type service_name str
    :param service: the service definition
    :type service: dict

    :return: depends_on, list of dependencies for the *Stack* object
    :rtype: list
    """
    from ecs_composex.ecs.ecs_networking import compile_network_settings
    depends_on = []
    links = service['links'] if KEYISSET('links', service) else []
    for dest_service in links:
        if KEYISSET(dest_service, compose_content[RES_KEY]):
            target_service = compose_content[RES_KEY][dest_service]
            if KEYISSET('ports', target_service):
                network_settings = compile_network_settings(
                    compose_content, target_service, dest_service
                )
                LOG.debug(network_settings)
                LOG.debug(f'Creating ingress rules for {service_name} to access {dest_service}')
                depends_on.append(dest_service)
                for port in network_settings['ports']:
                    SecurityGroupIngress(
                        f"From{service_name}To{dest_service}Port{port['target']}",
                        template=template,
                        SourceSecurityGroupOwnerId=Ref('AWS::AccountId'),
                        SourceSecurityGroupId=GetAtt(SG_T, 'GroupId'),
                        IpProtocol=port['protocol'],
                        FromPort=port['target'],
                        ToPort=port['target'],
                        GroupId=get_import_service_group_id(dest_service)
                    )
    LOG.debug(depends_on)
    return depends_on
