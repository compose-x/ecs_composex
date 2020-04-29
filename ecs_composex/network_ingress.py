# -*- coding: utf-8 -*-
"""
Module to handle TCP based access to resources network ingress.
"""

from ecs_composex.common import KEYISSET, LOG


SG_TO_MANY = 1
# SG TO MANY will add an ingress rule to the DB for each microservice security group listed.
SG_TO_ALL = 2
# SG TO ALL will create an additional security group that will be associated with the microservice.


def define_resource_strategy(resource):
    """

    :param resource:
    :return:
    """
    strategy = 0
    if not KEYISSET('Services', resource):
        return
    if KEYISSET("Settings", resource) and KEYISSET("is_global", resource["Settings"]):
        strategy = SG_TO_ALL
    if len(resource["Services"]) >= 40:
        LOG.info(f"Got more than 40 services. Globalizing to specified services")
        strategy = SG_TO_MANY
    return strategy


def generate_resource_ingress(resource_name, resource):
    """
    Function to generate a list of security group rules to add to the microservice.
    :param resource_name:
    :param resource:
    :return:
    """
    ingresses = {}
    services = resource['Services']
    for service in services:
        ingresses[service] = None
    return ingresses


def generate_restype_permissions(res_type, res_modname, resources):
    """
    Function to generate the ingress settings for a given resource type
    :param res_type:
    :param res_modname:
    :param resources:
    :return:
    """
    configs = {}
    for resource_name in resources:
        resource = resources[resource_name]
        if not KEYISSET("Services", resource):
            LOG.warn(f"{res_type} {resource_name} has no services defined. Skipping")
            continue
        strategy = define_resource_strategy(resource)
        if strategy == SG_TO_MANY:
            pass
