#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import ComposeService
    from ecs_composex.common.cfn_params import Parameter

from compose_x_common.aws.ecr import PRIVATE_ECR_URI_RE
from troposphere import Ref


class ServiceImage:
    def __init__(self, service: ComposeService, image_param: Parameter = None):
        self._service = service
        self._image_name = service.definition["image"]
        self._image_digest = None
        if not image_param:
            self.image = Parameter(
                f"{self.service.logical_name}ImageUrl", Type="String"
            )
        else:
            self.image = image_param

    @property
    def service(self) -> ComposeService:
        return self._service

    @property
    def image(self):
        return Ref(self._image_param)

    @image.setter
    def image(self, image_parameter: Parameter):
        self._image_param = image_parameter
        if self.service.container_definition:
            setattr(self.service.container_definition, "Image", self.image)

    @property
    def image_name(self) -> str:
        if not self._image_param.Type == r"AWS::SSM::Parameter::Value<String>":
            return self._image_name

    @property
    def ecr_properties(self) -> dict:
        parts = PRIVATE_ECR_URI_RE.match(self.image_name)
        if not parts:
            return {}
        tag = parts.group("tag")
        if tag.startswith(r"@sha"):
            image_id = {"imageDigest": tag}
        else:
            image_id = {"imageTag": tag}
        config: dict = {
            "RegistryId": parts.group("account_id"),
            "RepositoryName": parts.group("repo_name"),
            "Region": parts.group("region"),
        }
        config.update(image_id)
        return config
