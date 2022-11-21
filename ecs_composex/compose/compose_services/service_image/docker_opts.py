#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Helper functions around ECR and docker images, done early to ensure viability of the execution
before doing all the resources allocations / lookups
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.common.settings import ComposeXSettings

import warnings

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services.service_image.ecr_helpers import (
    define_service_image,
    interpolate_ecr_uri_tag_with_digest,
    invalidate_image_from_ecr,
)

try:
    from ecs_composex.compose.compose_services.service_image.ecr_scans_eval import (
        scan_service_image,
    )

    SCANS_POSSIBLE = True
except ImportError as error:
    SCANS_POSSIBLE = False
    warnings.warn(str(error))


def evaluate_ecr_configs(settings: ComposeXSettings) -> int:
    """
    Function to go over each service of each family in its final state and evaluate the ECR Image validity.
    """
    result = 0
    if not SCANS_POSSIBLE:
        return result
    for family in settings.families.values():
        for service in family.services:
            if not isinstance(service.image, str):
                continue
            if not keyisset("x-ecr", service.definition) or invalidate_image_from_ecr(
                service, True
            ):
                continue
            service_image = define_service_image(service, settings)
            if (
                service.ecr_config
                and keyisset("InterpolateWithDigest", service.ecr_config)
                and keyisset("imageDigest", service_image)
            ):
                service.image = interpolate_ecr_uri_tag_with_digest(
                    service.image, service_image["imageDigest"]
                )
                LOG.info(
                    f"Update service {family.name}.{service.name} image to {service.image}"
                )
            if scan_service_image(service, settings, service_image):
                LOG.warn(f"{family.name}.{service.name} - vulnerabilities found")
                result = 1
            else:
                LOG.info(f"{family.name}.{service.name} - ECR Evaluation Passed.")
    return result
