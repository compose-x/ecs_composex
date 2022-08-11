#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from os import path

from troposphere import AWS_PARTITION, Sub
from troposphere.ecs import EnvironmentFile
from troposphere.iam import PolicyType

import ecs_composex.common.troposphere_tools
from ecs_composex.common import FILE_PREFIX
from ecs_composex.common.files import upload_file
from ecs_composex.common.logging import LOG

# TODO: refactor policy by having a x-s3 Bucket object deal with permissions


def add_envfiles_bucket_iam_access(env_files, family, settings):
    if (
        env_files
        and family.template
        and "S3EnvFilesAccess" not in family.template.resources
    ):
        family.template.add_resource(
            PolicyType(
                "S3EnvFilesAccess",
                PolicyName="S3EnvFilesAccess",
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "s3:GetObject",
                            "Effect": "Allow",
                            "Resource": Sub(
                                f"arn:${{{AWS_PARTITION}}}:s3:::{settings.bucket_name}/*"
                            ),
                        }
                    ],
                },
                Roles=[
                    family.iam_manager.exec_role.name,
                    family.iam_manager.task_role.name,
                ],
            )
        )


def upload_services_env_files(family, settings) -> None:
    """
    Method to go over each service and if settings are to upload files to S3, will create objects and update the
    container definition for env_files accordingly.

    :param family:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    if settings.no_upload:
        return
    elif settings.for_cfn_macro:
        LOG.warning(
            f"{family.name} When running as a Macro, you cannot upload environment files."
        )
        return
    for service in family.services:
        env_files = []
        for env_file in service.env_files:
            with open(env_file) as file_fd:
                file_body = file_fd.read()
            object_name = path.basename(env_file)
            try:
                upload_file(
                    body=file_body,
                    bucket_name=settings.bucket_name,
                    mime="text/plain",
                    prefix=f"{FILE_PREFIX}/env_files",
                    file_name=object_name,
                    settings=settings,
                )
                LOG.info(
                    f"{family.name}.env_files - Successfully uploaded {env_file} to S3"
                )
            except Exception:
                LOG.error(f"Failed to upload env file {object_name}")
                raise
            file_path = Sub(
                f"arn:${{{AWS_PARTITION}}}:s3:::{settings.bucket_name}/{FILE_PREFIX}/env_files/{object_name}"
            )
            env_files.append(EnvironmentFile(Type="s3", Value=file_path))
        if not hasattr(service.container_definition, "EnvironmentFiles"):
            setattr(service.container_definition, "EnvironmentFiles", env_files)
        else:
            service.container_definition.EnvironmentFiles += env_files
        add_envfiles_bucket_iam_access(env_files, family, settings)
