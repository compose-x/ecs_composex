#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import re

from boto3.session import Session
from compose_x_common.aws.ecr.images import list_all_images
from compose_x_common.compose_x_common import keyisset, set_else_none

from ecs_composex.common.aws import get_cross_role_session
from ecs_composex.common.logging import LOG

ECR_URI_RE = re.compile(
    r"(?P<account_id>\d{12}).dkr.ecr.(?P<region>[a-z0-9-]+).amazonaws.com/"
    r"(?P<repo_name>[a-zA-Z0-9-_./]+)(?P<tag>(?:\@sha[\d]+:[a-z-Z0-9]+$)|(?::[\S]+$))"
)


def invalidate_image_from_ecr(service, mute=False):
    """
    Function to validate that the image URI is from valid and from private ECR

    :param ecs_composex.common.compose_services.ComposeService service:
    :param bool mute: Whether we display output
    :return: True when the image is not from ECR
    :rtype: bool
    """
    if not ECR_URI_RE.match(service.image.image_uri):
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


def define_ecr_session(account_id, repo_name, region, settings, role_arn=None):
    """
    Function to determine the boto3 session to use for subsequent API calls to ECR
    :param account_id:
    :param repo_name:
    :param region:
    :param settings:
    :param str role_arn:
    :return:
    """
    ecr_session = Session(region_name=region)
    current_account_id = settings.session.client("sts").get_caller_identity()["Account"]
    if account_id != current_account_id and role_arn is None:
        raise KeyError(
            f"The account for repository {repo_name} detected from image URI is in account "
            f"{account_id}, execution session in {current_account_id} and no RoleArn provided"
        )
    elif account_id != current_account_id and role_arn:
        ecr_session = get_cross_role_session(
            settings.session,
            role_arn,
            region_name=region,
            session_name="ecr-scan@compose-x",
        )
    return ecr_session


def identify_service_image(service, repo_name, image_sha, image_tag, session):
    """
    Function to identify the image in repository that matches the one defined in service
    for a private ECR Based image.

    :param str repo_name:
    :param str image_sha:
    :param str image_tag:
    :param boto3.session.Session session:
    :return: The image definition
    :rtype: dict
    """
    repo_images = list_all_images(repo_name=repo_name, ecr_session=session)
    for image in repo_images:
        if (
            image_sha
            and keyisset("imageDigest", image)
            and image["imageDigest"] == image_sha
        ) or (
            image_tag and keyisset("imageTag", image) and image["imageTag"] == image_tag
        ):
            return image
    else:
        raise LookupError(
            "Unable to find image",
            service.image.image_uri,
            "Deployment would result in failure.",
        )


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
    if not service.image.private_ecr:
        return
    image_sha = None
    image_tag = None
    parts = service.image.private_ecr
    tag = parts.group("tag")
    if tag.startswith(r":"):
        image_tag = tag.split(":")[-1]
    elif tag.startswith(r"@"):
        image_sha = tag.split("@")[-1]
    repo_name = parts.group("repo_name")
    account_id = parts.group("account_id")
    region = parts.group("region")
    session = define_ecr_session(
        account_id,
        repo_name,
        region,
        settings,
        role_arn=set_else_none("RoleArn", service.x_ecr),
    )
    the_image = identify_service_image(
        service, repo_name, image_sha, image_tag, session
    )
    return the_image
