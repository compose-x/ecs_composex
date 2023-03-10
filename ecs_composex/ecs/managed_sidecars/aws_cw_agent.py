#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Simple class to manage AWS XRay sidecar
"""

from copy import deepcopy

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.managed_sidecars import ManagedSidecar

CW_IMAGE_PARAMETER = Parameter(
    "CloudwatchAgentImage",
    Type="String",
    Default="public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest",
)

CW_AGENT_NAME = "cloudwatch-agent"
CW_AGENT_DEFINITION = {
    "image": CW_IMAGE_PARAMETER.Default,
    "ports": [
        {"target": 25888, "protocol": "tcp"},
        {"target": 25888, "protocol": "udp"},
    ],
    "deploy": {
        "resources": {"limits": {"cpus": 0.1, "memory": "256M"}},
    },
    "labels": {"container_name": CW_AGENT_NAME},
}


def get_cloudwatch_agent_sidecar(
    image_override: str = None, use_digest: bool = False
) -> ManagedSidecar:
    """Renders a new ManagedSidecar for the AWS CW Agent"""
    cw_agent_service_definition: dict = deepcopy(CW_AGENT_DEFINITION)
    if use_digest:
        cw_agent_service_definition.update(
            {"x-docker_opts": {"InterpolateWithDigest": True}}
        )
    if image_override:
        cw_agent_service_definition["image"] = image_override
    service = ManagedSidecar(CW_AGENT_NAME, cw_agent_service_definition)
    if use_digest:
        service.image.interpolate_image_digest()
    return service
