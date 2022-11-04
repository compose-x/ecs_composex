#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from compose_x_common.aws import get_account_id
from compose_x_common.compose_x_common import attributes_to_mapping, keyisset
from troposphere import GetAtt, Ref

from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.logging import LOG
from ecs_composex.common.settings import ComposeXSettings
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.compose.x_resources.api_x_resources import ApiXResource
from ecs_composex.kinesis_firehose.kinesis_firehose_stack import DeliveryStream
from ecs_composex.mods_manager import ModManager, XResourceModule
from ecs_composex.resource_settings import link_resource_to_services
from ecs_composex.s3.s3_ecs_cluster import handle_ecs_cluster
from ecs_composex.s3.s3_kinesis_firehose import s3_to_firehose
from ecs_composex.s3.s3_params import (
    CONTROL_CLOUD_ATTR_MAPPING,
    S3_BUCKET_ARN,
    S3_BUCKET_DOMAIN_NAME,
    S3_BUCKET_DUAL_STACK_NAME,
    S3_BUCKET_KMS_KEY,
    S3_BUCKET_KMS_KEY_ARN,
    S3_BUCKET_NAME,
    S3_BUCKET_REGION_DOMAIN_NAME,
)


class Bucket(ApiXResource):
    """
    Class for S3 bucket.
    """

    def __init__(
        self, name, definition, module: XResourceModule, settings: ComposeXSettings
    ):
        super().__init__(name, definition, module, settings)
        self.cloud_control_attributes_mapping = CONTROL_CLOUD_ATTR_MAPPING
        self.kms_arn_attr = S3_BUCKET_KMS_KEY_ARN
        self.arn_parameter = S3_BUCKET_ARN
        self.ref_parameter = S3_BUCKET_NAME

        self.default_cloudmap_settings = {
            "ReturnValues": {
                S3_BUCKET_NAME.title: S3_BUCKET_NAME.title,
                S3_BUCKET_ARN.title: S3_BUCKET_ARN.title,
                S3_BUCKET_DOMAIN_NAME.return_value: S3_BUCKET_NAME.return_value,
            }
        }
        self.cloudmap_dns_supported = False
        self.support_defaults = True

    def init_outputs(self):
        self.output_properties = {
            S3_BUCKET_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            S3_BUCKET_ARN: (
                f"{self.logical_name}{S3_BUCKET_ARN.title}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_ARN.return_value,
            ),
            S3_BUCKET_DOMAIN_NAME: (
                f"{self.logical_name}{S3_BUCKET_DOMAIN_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_DOMAIN_NAME.return_value,
                None,
            ),
            S3_BUCKET_DUAL_STACK_NAME: (
                f"{self.logical_name}{S3_BUCKET_DUAL_STACK_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_DUAL_STACK_NAME.return_value,
                None,
            ),
            S3_BUCKET_REGION_DOMAIN_NAME: (
                f"{self.logical_name}{S3_BUCKET_REGION_DOMAIN_NAME.return_value}",
                self.cfn_resource,
                GetAtt,
                S3_BUCKET_REGION_DOMAIN_NAME.return_value,
                None,
            ),
        }

    def native_attributes_mapping_lookup(self, account_id, resource_id, function):
        properties = function(self, resource_id)
        if self.native_attributes_mapping:
            conform_mapping = attributes_to_mapping(
                properties, self.native_attributes_mapping
            )
            return conform_mapping
        return properties

    def lookup_resource(
        self,
        arn_re,
        native_lookup_function,
        cfn_resource_type,
        tagging_api_id,
        subattribute_key=None,
    ):
        """
        Method to self-identify properties
        :return:
        """
        if keyisset("Arn", self.lookup):
            arn_parts = arn_re.match(self.lookup["Arn"])
            if not arn_parts:
                raise KeyError(
                    f"{self.module.res_key}.{self.name} - ARN {self.lookup['Arn']} is not valid. Must match",
                    arn_re.pattern,
                )
            self.arn = self.lookup["Arn"]
            resource_id = arn_parts.group("id")
        elif keyisset("Tags", self.lookup):
            self.arn = find_aws_resource_arn_from_tags_api(
                self.lookup, self.lookup_session, tagging_api_id
            )
            arn_parts = arn_re.match(self.arn)
            resource_id = arn_parts.group("id")
        else:
            raise KeyError(
                f"{self.module.res_key}.{self.name} - You must specify Arn or Tags to identify existing resource"
            )
        if not self.arn:
            raise LookupError(
                f"{self.module.res_key}.{self.name} - Failed to find the AWS Resource with given tags"
            )
        props = {}
        if self.cloud_control_attributes_mapping:
            _s3 = self.lookup_session.resource("s3")
            try:
                if _s3.Bucket(resource_id) in _s3.buckets.all():
                    props = self.cloud_control_attributes_mapping_lookup(
                        cfn_resource_type, resource_id
                    )
            except _s3.meta.client.exceptions:
                LOG.warning(
                    f"{self.module.res_key}.{self.name} - Failed to evaluate bucket ownership. Cannot use Control API"
                )
        if not props:
            props = self.native_attributes_mapping_lookup(
                get_account_id(self.lookup_session), resource_id, native_lookup_function
            )
        self.lookup_properties = props
        self.generate_cfn_mappings_from_lookup_properties()

    def to_ecs(
        self,
        settings: ComposeXSettings,
        modules: ModManager,
        root_stack: ComposeXStack = None,
        targets_overrides: list = None,
    ):
        """
        Handles mapping the S3 bucket to ECS services
        """
        LOG.info(f"{self.module.res_key}.{self.name} - Linking to services")
        link_resource_to_services(
            settings,
            self,
            arn_parameter=S3_BUCKET_ARN,
            access_subkeys=["objects", "bucket", "enforceSecureConnection"],
            targets_overrides=targets_overrides,
        )

    def handle_x_dependencies(
        self, settings: ComposeXSettings, root_stack: ComposeXStack
    ) -> None:
        """

        :param settings:
        :param root_stack:
        :return:
        """
        handle_ecs_cluster(settings, bucket=self)
        for resource in settings.get_x_resources(include_mappings=False):
            if not resource.cfn_resource:
                continue
            if not resource.stack:
                LOG.debug(
                    f"resource {resource.name} has no `stack` attribute defined. Skipping"
                )
                continue
            mappings = [(DeliveryStream, s3_to_firehose)]
            for target in mappings:
                if isinstance(resource, target[0]) or issubclass(
                    type(resource), target[0]
                ):
                    target[1](
                        self,
                        resource,
                        resource.stack,
                        settings,
                    )
