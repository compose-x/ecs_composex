#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Helper functions around ECR and docker images, done early to ensure viability of the execution
before doing all the resources allocations / lookups
"""

import re
import warnings

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG

try:
    from ecs_composex.compose.compose_services.service_image.ecr_scans_eval import (
        define_service_image,
        interpolate_ecr_uri_tag_with_digest,
        invalidate_image_from_ecr,
        scan_service_image,
    )

    SCANS_POSSIBLE = True
except ImportError:
    warnings.warn(
        "You must install ecs-composex[ecrscan] extra to use this functionality"
    )
    SCANS_POSSIBLE = False


def evaluate_ecr_configs(settings) -> int:
    """
    Function to go over each service of each family in its final state and evaluate the ECR Image validity.

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return:
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


def evaluate_docker_configs(settings):
    """
    Function to go over the services settings and evaluate x-docker

    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return:
    """
    image_tag_re = re.compile(r"(?P<tag>(?:\@sha[\d]+:[a-z-Z0-9]+$)|(?::[\S]+$))")
    for family in settings.families.values():
        for service in family.services:
            if not keyisset("x-docker_opts", service.definition):
                continue
            docker_config = service.definition["x-docker_opts"]
            if SCANS_POSSIBLE:
                if keyisset("InterpolateWithDigest", docker_config):
                    if not invalidate_image_from_ecr(service, mute=True):
                        LOG.warn(
                            "You set InterpolateWithDigest to true for x-docker for an image in AWS ECR."
                            "Please refer to x-ecr"
                        )
                        continue
                else:
                    warnings.warn(
                        "Run pip install ecs_composex[ecrscan] to use x-ecr features"
                    )
                service.retrieve_image_digest()
                if service.image_digest:
                    service.image = image_tag_re.sub(
                        f"@{service.image_digest}", service.image
                    )
                    LOG.info(f"Successfully retrieved digest for {service.name}.")
                    LOG.info(f"{service.name} - {service.image}")
