#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Simple class to manage AWS XRay sidecar
"""

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
    "ports": [{"target": 25888, "protocol": "tcp"}],
    "deploy": {
        "resources": {"limits": {"cpus": 0.1, "memory": "256M"}},
    },
    "labels": {"container_name": CW_AGENT_NAME},
}

CW_AGENT_SERVICE = ManagedSidecar(CW_AGENT_NAME, CW_AGENT_DEFINITION)
