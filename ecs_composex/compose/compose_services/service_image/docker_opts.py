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

from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common.logging import LOG
from ecs_composex.compose.compose_services.service_image.ecr_helpers import (
    define_service_image,
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
    if not SCANS_POSSIBLE:
        return 0
    for family in settings.families.values():
        for service in family.services:
            x_ecr_config = set_else_none("x-ecr", service.definition)

            if not x_ecr_config or not service.image.private_ecr:
                LOG.debug(
                    "{}.{} - Not private ECR nor valid".format(
                        family.name, service.name
                    )
                )
                continue
            service_image = define_service_image(service, settings)
            scan_pass, findings, failed_findings = scan_service_image(
                service, settings, service_image
            )
            LOG.debug("%s %s %s", scan_pass, findings, failed_findings)
            if scan_pass and not findings:
                LOG.info(
                    f"{family.name}.{service.name} - ECR Scan Pass (No vulnerabilities found)"
                )
                return 0
            if findings:
                LOG.warn(
                    "{}.{} - ECR Scan Findings(LEVEL:findings/threshold): {}".format(
                        family.name, service.name, "|".join(findings)
                    )
                )
                if failed_findings:
                    LOG.error(
                        "{}.{} - Findings above thresholds: {}".format(
                            family.name, service.name, "|".join(failed_findings)
                        )
                    )
            if not scan_pass and not settings.ignore_ecr_findings:
                LOG.error(f"{family.name}.{service.name} - vulnerabilities found")
                return 1
    return 0
