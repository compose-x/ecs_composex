#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

import re
from time import sleep
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from ecs_composex.compose.compose_services.service_image import ServiceImage

from boto3.session import Session
from compose_x_common.compose_x_common import keyisset, set_else_none

try:
    from ecr_scan_reporter.ecr_scan_reporter import DEFAULT_THRESHOLDS
    from ecr_scan_reporter.images_scanner import trigger_images_scan
except ImportError:
    DEFAULT_THRESHOLDS: dict = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    raise ImportError(
        "Run pip install ecs-composex[ecrscan] to enable this functionality."
    )
from ecs_composex.common.logging import LOG

from .ecr_helpers import define_ecr_session

ECR_URI_RE = re.compile(
    r"(?P<account_id>\d{12}).dkr.ecr.(?P<region>[a-z0-9-]+).amazonaws.com/"
    r"(?P<repo_name>[a-zA-Z0-9-_./]+)(?P<tag>(?:\@sha[\d]+:[a-z-Z0-9]+$)|(?::[\S]+$))"
)


def initial_scan_retrieval(
    registry, repository_name, image, service_image, trigger_scan, ecr_session=None
):
    """
    Function to retrieve the scan findings from ECR, and if none, can trigger scan

    :param str registry:
    :param str repository_name:
    :param dict image:
    :param ServiceImage service_image:
    :param bool trigger_scan:
    :param boto3.session.Session ecr_session:
    :return: The scan report
    :rtype: dict
    """
    if ecr_session is None:
        ecr_session = Session()
    client = ecr_session.client("ecr")
    try:
        image_scan_r = client.describe_image_scan_findings(
            registryId=registry, repositoryName=repository_name, imageId=image
        )
        return image_scan_r
    except client.exceptions.ScanNotFoundException:
        LOG.warning(f"No scan report found for {service_image.image_uri}")
        if trigger_scan:
            LOG.info(
                f"Triggering scan for {service_image.image_uri}, trigger_scan={trigger_scan}"
            )
            trigger_images_scan(
                repo_name=repository_name,
                images_to_scan=[image],
                ecr_session=ecr_session,
            )
        else:
            LOG.warn(
                f"No scan was available and scanning not requested for {service_image.image_uri}. Skipping"
            )
            return None


def scan_poll_and_wait(
    registry,
    repository_name,
    image,
    image_url,
    ecr_session=None,
    scan_frequency: str = None,
    scan_on_push: bool = False,
):
    """Function to pull the scans results until no longer in progress"""
    client = ecr_session.client("ecr")
    while True:
        try:
            image_scan_r = client.describe_image_scan_findings(
                registryId=registry,
                repositoryName=repository_name,
                imageId=image,
            )
            if image_scan_r["imageScanStatus"]["status"] in ["IN_PROGRESS", "PENDING"]:
                LOG.info(
                    f"{image_url.image_uri} - Scan in progress - waiting 10 seconds"
                )
                sleep(10)
            else:
                return image_scan_r
        except client.exceptions.ScanNotFoundException:
            if scan_frequency and scan_frequency == "CONTINUOUS_SCAN" and scan_on_push:
                LOG.info(f"{image_url.image_uri} - Pending enhanced scan")
                sleep(10)
        except client.exceptions.LimitExceededException:
            LOG.warn(f"{image_url} - Exceeding API Calls quota. Waiting 10 seconds")
            sleep(10)


def wait_for_scan_report(
    registry,
    repository_name,
    image,
    image_url: ServiceImage,
    trigger_scan=False,
    ecr_session=None,
) -> dict[str, Union[dict, str]]:
    """
    Function to wait for the scan report to go from In Progress to else

    :param str registry:
    :param str repository_name:
    :param image:
    :param str image_url::
    :param bool trigger_scan:
    :param boto3.session.Session ecr_session:
    :return:
    """
    if not ecr_session:
        ecr_session = Session()
    findings = {}
    scan_frequency = None
    scan_on_push = False
    try:
        scanning_config = ecr_session.client(
            "ecr"
        ).batch_get_repository_scanning_configuration(
            repositoryNames=[repository_name]
        )[
            "scanningConfigurations"
        ]
        scan_frequency = scanning_config[0]["scanFrequency"]
        scan_on_push = scanning_config[0]["scanOnPush"]
    except Exception as error:
        LOG.warning(
            f"{repository_name} - Could not determine scanning configuration - {error}"
        )
    image_scan_r = initial_scan_retrieval(
        registry, repository_name, image, image_url, trigger_scan, ecr_session
    )
    LOG.info(
        "ECR Repository Scan configuration: {} - (ScanOnPush/scanFrequency): {}/{}".format(
            repository_name, scan_on_push, scan_frequency
        )
    )
    if (
        image_scan_r is None
        and not trigger_scan
        and scan_frequency != "CONTINUOUS_SCAN"
    ):
        return findings
    if (image_scan_r is None and scan_frequency == "CONTINUOUS_SCAN") or (
        image_scan_r
        and (
            keyisset("imageScanStatus", image_scan_r)
            and image_scan_r["imageScanStatus"]["status"] in ["IN_PROGRESS", "PENDING"]
        )
    ):
        image_scan_r = scan_poll_and_wait(
            registry,
            repository_name,
            image,
            image_url,
            ecr_session,
            scan_frequency,
            scan_on_push,
        )

    if image_scan_r is None:
        reason = "Failed to retrieve or poll scan report"
        LOG.error(reason)
        findings: dict = {"FAILED": True, "reason": reason}
    elif image_scan_r["imageScanStatus"]["status"] != "FAILED" and keyisset(
        "findingSeverityCounts", image_scan_r["imageScanFindings"]
    ):
        findings: dict = image_scan_r["imageScanFindings"]["findingSeverityCounts"]
    elif image_scan_r["imageScanStatus"]["status"] == "FAILED":
        findings: dict = {
            "FAILED": True,
            "reason": image_scan_r["imageScanStatus"]["description"],
        }
    return findings


def validate_input(service):
    """
    Validates that we have enough settings and the URL matches AWS ECR Private Repo

    :param ecs_composex.common.compose_services.ComposeService service:
    :return:
    """
    if not service.ecr_config:
        LOG.debug(f"No configuration defined for x-ecr. Skipping for {service.name}")
        return True
    if not keyisset("VulnerabilitiesScan", service.ecr_config):
        LOG.info(f"{service.name} - No scan to be evaluated.")
        return True
    return False


def define_result(
    image_url: str,
    security_findings: dict,
    thresholds: dict,
    vulnerability_config: dict,
) -> tuple[bool, list[str], list[str]]:
    """
    Function to define what to do with findings, if any.
    If VulnerabilitiesScan.Fail is False, then ignore the findings and display only

    :param str image_url:
    :param dict security_findings:
    :param dict thresholds:
    :param dict vulnerability_config:
    :return: Whether there is a breach of thresholds or not
    :rtype: bool
    """
    results: list[str] = []
    over_the_limit_results: list[str] = []
    ignore = keyisset("IgnoreFailure", vulnerability_config)
    if not security_findings:
        return True, results, over_the_limit_results
    elif keyisset("FAILED", security_findings):
        LOG.error(
            f"{image_url} - Scan of image failed. - {security_findings['reason']}"
        )
        treat_failed_as = set_else_none(
            "TreatFailedAs", vulnerability_config, "Failure"
        )
        if treat_failed_as == "Success":
            LOG.warning("TreatFailedAs set to Success - ignoring scan failure")
            return True, results, over_the_limit_results
        else:
            return False, results, over_the_limit_results
    else:
        for name, limit in thresholds.items():
            level_limit = set_else_none(name, security_findings)
            if not level_limit:
                continue
            if level_limit > limit:
                over_the_limit_results.append(f"{name}: {level_limit}/{limit}")
            results.append(f"{name}: {level_limit}/{limit}")
    if not ignore and over_the_limit_results:
        return False, results, over_the_limit_results
    return True, results, over_the_limit_results


def validate_the_image_input(the_image):
    """
    Function to validet the_image input

    :param dict the_image:
    :raises: ValueError if is None
    :raises: TypeError if the_image is not dict
    :raises: KeyError if imageDigest is missing
    """
    if the_image is None:
        raise ValueError("You must provide the image information")
    elif not isinstance(the_image, dict):
        raise TypeError("the_image must be of type", dict, "got", type(the_image))
    elif not keyisset("imageDigest", the_image):
        raise KeyError("imageDigest must be set in the_image")


def scan_service_image(
    service, settings, the_image: dict = None
) -> tuple[bool, list[str], list[str]]:
    """
    Function to review the service definition and evaluate scan if properties defined

    :param ecs_composex.common.compose_services.ComposeService service:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :param the_image: The image to use for scanning references.
    """
    region = None
    if validate_input(service):
        return True, [], []
    vulnerability_config = service.ecr_config["VulnerabilitiesScan"]
    if keyisset("Thresholds", vulnerability_config):
        thresholds = dict(DEFAULT_THRESHOLDS)
        thresholds.update(vulnerability_config["Thresholds"])
    else:
        LOG.warn(f"No thresholds defined. Using defaults {DEFAULT_THRESHOLDS}")
        thresholds = DEFAULT_THRESHOLDS
    validate_the_image_input(the_image)
    parts = service.image.private_ecr
    repo_name = parts.group("repo_name")
    account_id = parts.group("account_id")
    region = parts.group("region")
    session = define_ecr_session(
        account_id,
        repo_name,
        region,
        settings,
        role_arn=service.ecr_config["RoleArn"]
        if keyisset("RoleArn", vulnerability_config)
        else None,
    )
    security_findings = wait_for_scan_report(
        registry=account_id,
        repository_name=repo_name,
        image=the_image,
        image_url=service.image,
        ecr_session=session,
    )
    return define_result(
        service.image, security_findings, thresholds, vulnerability_config
    )
