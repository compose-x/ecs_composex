#   -*- coding: utf-8 -*-
#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2021 John Mille <john@compose-x.io>

import re
from time import sleep

from boto3.session import Session

try:
    from ecr_scan_reporter.ecr_scan_reporter import DEFAULT_THRESHOLDS
    from ecr_scan_reporter.images_scanner import list_all_images, trigger_images_scan
except ImportError:
    raise ImportError(
        "You must install ecr-scan-reporter in order to use this functionality"
    )

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common import LOG
from ecs_composex.common.aws import get_cross_role_session

ECR_URI_RE = re.compile(
    r"(?P<account_id>\d{12}).dkr.ecr.(?P<region>[a-z0-9-]+).amazonaws.com/"
    r"(?P<repo_name>[a-zA-Z0-9-_./]+)(?P<tag>(?:\@sha[\d]+:[a-z-Z0-9]+$)|(?::[\S]+$))"
)


def initial_scan_retrieval(
    registry, repository_name, image, image_url, trigger_scan, ecr_session=None
):
    """
    Function to retrieve the scan findings from ECR, and if none, can trigger scan

    :param str registry:
    :param str repository_name:
    :param dict image:
    :param str image_url:
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
        LOG.error(f"No scan report found for {image_url}")
        if trigger_scan:
            LOG.info(f"Triggering scan for {image_url}, trigger_scan={trigger_scan}")
            trigger_images_scan(
                repo_name=repository_name,
                images_to_scan=[image],
                ecr_session=ecr_session,
            )
        else:
            LOG.warn(
                f"No scan was available and scanning not requested for {image_url}. Skipping"
            )
            return None


def scan_poll_and_wait(registry, repository_name, image, image_url, ecr_session=None):
    """
    Function to pull the scans results until no longer in progress

    :param boto3.session.Session ecr_session:
    :param registry:
    :param repository_name:
    :param image:
    :param image_url:
    :param ecr_session:
    :return: The scan report
    :rtype: dict
    """
    client = ecr_session.client("ecr")
    while True:
        try:
            image_scan_r = client.describe_image_scan_findings(
                registryId=registry,
                repositoryName=repository_name,
                imageId=image,
            )
            if image_scan_r["imageScanStatus"]["status"] == "IN_PROGRESS":
                LOG.info(f"{image_url} - Scan in progress - waiting 10 seconds")
                sleep(10)
            else:
                return image_scan_r
        except client.exceptions.LimitExceededException:
            LOG.warn(f"{image_url} - Exceeding API Calls quota. Waiting 10 seconds")
            sleep(10)


def wait_for_scan_report(
    registry,
    repository_name,
    image,
    image_url,
    trigger_scan=False,
    ecr_session=None,
):
    """
    Function to wait for the scan report to go from In Progress to else

    :param str registry:
    :param str repository_name:
    :param dict image:
    :param str image_url::
    :param bool trigger_scan:
    :param boto3.session.Session ecr_session:
    :return:
    """
    if not ecr_session:
        ecr_session = Session()
    findings = {}
    image_scan_r = initial_scan_retrieval(
        registry, repository_name, image, image_url, trigger_scan, ecr_session
    )
    if (
        image_scan_r
        and keyisset("imageScanStatus", image_scan_r)
        and image_scan_r["imageScanStatus"]["status"] == "IN_PROGRESS"
    ):
        image_scan_r = scan_poll_and_wait(
            registry, repository_name, image, image_url, ecr_session
        )
    if image_scan_r is None:
        reason = "Failed to retrieve or poll scan report"
        LOG.error(reason)
        return {"FAILED": True, "reason": reason}
    if image_scan_r["imageScanStatus"]["status"] == "COMPLETE" and keyisset(
        "findingSeverityCounts", image_scan_r["imageScanFindings"]
    ):
        findings = image_scan_r["imageScanFindings"]["findingSeverityCounts"]
    elif image_scan_r["imageScanStatus"]["status"] == "FAILED":
        findings = {
            "FAILED": True,
            "reason": image_scan_r["imageScanStatus"]["description"],
        }
    return findings


def invalidate_image_from_ecr(service, mute=False):
    """
    Function to validate that the image URI is from valid and from private ECR

    :param ecs_composex.common.compose_services.ComposeService service:
    :param bool mute: Whether we display output
    :return: True when the image is not from ECR
    :rtype: bool
    """
    if not ECR_URI_RE.match(service.image):
        if not mute:
            LOG.info(
                f"{service.name} - image provided not valid ECR URI - "
                f"{service.image} - "
            )
            LOG.info(f"Expected ECR Regexp {ECR_URI_RE.pattern}")
        return True
    return False


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
    if invalidate_image_from_ecr(service, True):
        return True
    return False


def define_ecr_session(
    account_id, current_account_id, repo_name, region, settings, role_arn=None
):
    """
    Function to determine the boto3 session to use for subsequent API calls to ECR
    :param account_id:
    :param current_account_id:
    :param repo_name:
    :param region:
    :param settings:
    :param str role_arn:
    :return:
    """
    session = Session(region_name=region)
    if account_id != current_account_id and role_arn is None:
        raise KeyError(
            f"The account for repository {repo_name} detected from image URI is in account "
            f"{account_id}, execution session in {current_account_id} and no RoleArn provided"
        )
    elif account_id != current_account_id and role_arn:
        session = get_cross_role_session(
            settings.session,
            role_arn,
            region_name=region,
            session_name="ecr-scan@compose-x",
        )
    return session


def identify_service_image(repo_name, image_sha, image_tag, session):
    """
    Function to identify the image in repository that matches the one defined in services.image

    :param str repo_name:
    :param str image_sha:
    :param str image_tag:
    :param boto3.session.Session session:
    :return: The image definition
    :rtype: dict
    """
    repo_images = list_all_images(repo_name=repo_name, ecr_session=session)
    the_image = None
    for image in repo_images:
        if (
            image_sha
            and keyisset("imageDigest", image)
            and image["imageDigest"] == image_sha
        ) or (
            image_tag and keyisset("imageTag", image) and image["imageTag"] == image_tag
        ):
            the_image = image
    return the_image


def define_result(image_url, security_findings, thresholds, vulnerability_config):
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
    result = False
    if not security_findings:
        return result
    elif keyisset("FAILED", security_findings):
        LOG.error(
            f"{image_url} - Scan of image failed. - {security_findings['reason']}"
        )
        if keyisset("TreatFailedAs", vulnerability_config):
            if vulnerability_config["TreatFailedAs"] == "Success":
                LOG.info("TreatFailedAs set to Success - ignoring scan failure")
                result = False
            else:
                result = True
    else:
        for name, limit in thresholds.items():
            if keyisset(name, security_findings) and security_findings[name] >= limit:
                LOG.error(
                    f"Found {name} vulnerability: {security_findings[name]}/{limit}"
                )
                if not keyisset("IgnoreFailure", vulnerability_config):
                    result = True
    LOG.info("ECR Scan Thresholds")
    LOG.info(",".join([f"{name}/{limit}" for name, limit in thresholds.items()]))
    return result


def interpolate_ecr_uri_tag_with_digest(image_url, image_digest):
    """
    Function to replace the tag from image_url

    :param str image_url:
    :param str image_digest:
    :return:
    """
    tag = ECR_URI_RE.match(image_url).group("tag")
    if tag.startswith(r"@"):
        return image_url
    new_image = re.sub(tag, f"@{image_digest}", image_url)
    return new_image


def define_service_image(service, settings):
    """
    Function to parse and identify the image for the service in AWS ECR

    :param ecs_composex.common.compose_services.ComposeService service:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :return:
    """
    current_account_id = settings.session.client("sts").get_caller_identity()["Account"]
    if invalidate_image_from_ecr(service):
        return
    image_sha = None
    image_tag = None
    tag = ECR_URI_RE.match(service.image).group("tag")
    if tag.startswith(r":"):
        image_tag = tag.split(":")[-1]
    elif tag.startswith(r"@"):
        image_sha = tag.split("@")[-1]
    repo_name = ECR_URI_RE.match(service.image).group("repo_name")
    account_id = ECR_URI_RE.match(service.image).group("account_id")
    region = ECR_URI_RE.match(service.image).group("region")
    session = define_ecr_session(
        account_id,
        current_account_id,
        repo_name,
        region,
        settings,
        role_arn=service.ecr_config["RoleArn"]
        if keyisset("RoleArn", service.ecr_config)
        else None,
    )
    the_image = identify_service_image(repo_name, image_sha, image_tag, session)
    return the_image


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


def scan_service_image(service, settings, the_image=None):
    """
    Function to review the service definition and evaluate scan if properties defined

    :param ecs_composex.common.compose_services.ComposeService service:
    :param ecs_composex.common.settings.ComposeXSettings settings: The settings for the execution
    :param the_image: The image to use for scanning references.
    :return:
    """
    region = None
    current_account_id = settings.session.client("sts").get_caller_identity()["Account"]
    if validate_input(service):
        return
    vulnerability_config = service.ecr_config["VulnerabilitiesScan"]
    if keyisset("Thresholds", vulnerability_config):
        thresholds = dict(DEFAULT_THRESHOLDS)
        thresholds.update(vulnerability_config["Thresholds"])
    else:
        LOG.warn(f"No thresholds defined. Using defaults {DEFAULT_THRESHOLDS}")
        thresholds = DEFAULT_THRESHOLDS
    validate_the_image_input(the_image)
    repo_name = ECR_URI_RE.match(service.image).group("repo_name")
    account_id = ECR_URI_RE.match(service.image).group("account_id")
    region = ECR_URI_RE.match(service.image).group("region")
    session = define_ecr_session(
        account_id,
        current_account_id,
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
