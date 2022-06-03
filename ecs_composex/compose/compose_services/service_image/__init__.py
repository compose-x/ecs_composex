#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

import re
from typing import TYPE_CHECKING, Union

from boto3.session import Session
from botocore.exceptions import ClientError

if TYPE_CHECKING:
    from . import ComposeService

import warnings

try:
    import docker

    USE_DOCKER = True
except ImportError:
    USE_DOCKER = False
    warnings.warn(
        "Due to security issues not addressed by docker python, this is temporarily disabled.",
        DeprecationWarning,
    )
import requests
import urllib3
from compose_x_common.aws import get_session
from compose_x_common.aws.ecr import PRIVATE_ECR_URI_RE, PUBLIC_ECR_URI_RE
from compose_x_common.compose_x_common import keyisset
from troposphere import Ref

from ecs_composex.common import LOG
from ecs_composex.common.cfn_params import Parameter


def get_image_from_ssm_parameter(
    ssm_parameter: Parameter, session: Session = None
) -> Union[str, None]:
    session = get_session(session)
    client = session.client("ssm")
    try:
        return client.get_parameter(Name=ssm_parameter.Default)["Parameter"]["Value"]
    except (client.exceptions.InvalidKeyId, client.exceptions.ParameterNotFound):
        pass
    except ClientError:
        pass
    return None


class ServiceImage:
    """

    :ivar _image:
    :ivar str image_name:
    """

    def __init__(self, service: ComposeService, image_param: Parameter = None):
        if not keyisset("image", service.definition):
            raise KeyError(service.name, "You must define ``image``")
        self._service = service
        self._image = None

        self.image_name = service.definition["image"]
        if not image_param:
            self._image_param = Parameter(
                f"{self.service.logical_name}ImageUrl", Type="String"
            )
            self.image = service.definition["image"]
        else:
            self._image_param = image_param
            self.image = image_param

    @property
    def image(self) -> Union[str, Ref]:
        if isinstance(self._image, str):
            return self._image
        elif isinstance(self._image, Parameter):
            return Ref(self._image)

    @image.setter
    def image(self, value: Union[str, Parameter]):
        if isinstance(value, str):
            self._image = value
        elif isinstance(value, Parameter):
            self._image = self.image_param
        else:
            raise TypeError(
                self.service,
                "image must be one of",
                (str, Parameter),
                "Got",
                value,
                type(value),
            )

    @property
    def image_param(self) -> Parameter:
        return self._image_param

    @property
    def service(self) -> ComposeService:
        return self._service

    @property
    def private_ecr(self) -> Union[re.Match, None]:
        return PRIVATE_ECR_URI_RE.match(self.image_name)

    @property
    def public_ecr(self) -> Union[re.Match, None]:
        return PUBLIC_ECR_URI_RE.match(self.image_name)

    @property
    def ecr_properties(self) -> dict:
        ecr_private_parts = self.private_ecr
        ecr_public_parts = self.public_ecr
        if ecr_private_parts:
            tag = ecr_private_parts.group("tag")
            if tag.startswith(r"@sha"):
                image_id = {"imageDigest": tag}
            else:
                image_id = {"imageTag": tag}
            config: dict = {
                "RegistryId": ecr_private_parts.group("account_id"),
                "RepositoryName": ecr_private_parts.group("repo_name"),
                "Region": ecr_private_parts.group("region"),
            }
            config.update(image_id)
            return config
        elif ecr_public_parts:
            tag = ecr_public_parts.group("tag")
            if tag.startswith(r"@sha"):
                image_id = {"imageDigest": tag}
            else:
                image_id = {"imageTag": tag}
            config: dict = {
                "RepositoryName": ecr_public_parts.group("repo_name"),
                "Region": "us-east-1",
            }
            config.update(image_id)
            return config
        else:
            return {}

    def retrieve_image_digest(self):
        """
        Retrieves the docker images digest from the repository to use instead of the image tag.
        """
        if isinstance(self.image, Ref):
            return
        valid_media_types = [
            "application/vnd.docker.distribution.manifest.v1+json",
            "application/vnd.docker.distribution.manifest.v2+json",
            "application/vnd.docker.distribution.manifest.v1+prettyjws",
            "application/vnd.docker.distribution.manifest.list.v2+json",
        ]
        if not USE_DOCKER:
            return
        try:
            dkr_client = docker.APIClient()
            image_details = dkr_client.inspect_distribution(self.image)
            if not keyisset("Descriptor", image_details):
                raise KeyError(f"No information retrieved for {self.image}")
            details = image_details["Descriptor"]
            if (
                keyisset("mediaType", details)
                and details["mediaType"] not in valid_media_types
            ):
                raise ValueError(
                    "The mediaType is not valid. Got",
                    details["mediaType"],
                    "Expected one of",
                    valid_media_types,
                )
            if keyisset("digest", details):
                self.image_digest = details["digest"]
            else:
                LOG.warning(
                    "No digest found. This might be due to Registry API prior to V2"
                )

        except (docker.errors.APIError, docker.errors.DockerException) as error:
            LOG.error(f"Failed to retrieve the image digest for {self.image}")
            print(error)
        except (FileNotFoundError, urllib3.exceptions, requests.exceptions):
            LOG.error("Failed to connect to any docker engine.")
