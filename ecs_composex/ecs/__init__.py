# -*- coding: utf-8 -*-
"""
Core module for ECS ComposeX.

This module is going to parse each service and each x-resource key from the compose file
(hence ComposeX) and determine its

* ServiceDefinition
* TaskDefinition
* TaskRole
* ExecutionRole

It is going to also, based on the labels set in the compose file

* Add the service to Service Discovery via AWS CloudMap
* Add load-balancers to dispatch traffic to the microservice

"""

import boto3

from ecs_composex.common import load_composex_file
from ecs_composex.ecs.ecs_template import generate_services_templates


def create_services_templates(session=None, **kwargs):
    """
    :return:
    """
    if session is None:
        session = boto3.session.Session()
    content = load_composex_file(kwargs['ComposeXFile'])
    services_template = generate_services_templates(
        compose_content=content, session=session,
        **kwargs
    )
    return services_template
