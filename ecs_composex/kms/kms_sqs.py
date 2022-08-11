#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Handle x-kms in x-sqs
"""

from troposphere import Ref

from ..common.troposphere_tools import add_parameters, add_update_mapping
from .kms_params import KMS_KEY_ID

KEY = "KmsMasterKeyId"


def assign_kms_key_to_queue(kms_key, queue, queue_stack, settings):
    """
    Assigns the KMS Key pointer to the queue property

    :param ecs_composex.kms.kms_stack.KmsKey kms_key:
    :param queue:
    :param ecs_composex.sqs.sqs_stack.XStack queue_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """
    kms_key_id = kms_key.attributes_outputs[KMS_KEY_ID]
    if kms_key.cfn_resource:
        add_parameters(queue_stack.stack_template, [kms_key_id["ImportParameter"]])
        setattr(
            queue.cfn_resource,
            KEY,
            Ref(kms_key_id["ImportParameter"]),
        )
        queue_stack.Parameters.update(
            {kms_key_id["ImportParameter"].title: kms_key_id["ImportValue"]}
        )
    elif not kms_key.cfn_resource and kms_key.mappings:
        add_update_mapping(
            queue.stack.stack_template,
            kms_key.module.mapping_key,
            settings.mappings[kms_key.module.mapping_key],
        )
        setattr(queue.cfn_resource, KEY, kms_key_id["ImportValue"])


def handle_queue_kms(kms_key, queue, queue_stack, settings):
    """
    Goes over the properties of the queue and if the KEY points to the kms_key,
    assigns the value accordingly in the template

    :param ecs_composex.kms.kms_stack.KmsKey kms_key:
    :param ecs_composex.sqs.sqs_stack.Queue queue:
    :param ecs_composex.sqs.sqs_stack.XStack queue_stack:
    :param ecs_composex.common.settings.ComposeXSettings settings:
    :return:
    """

    if not queue.cfn_resource:
        LOG.debug(f"{queue.module.res_key}.{queue.name} - Not a new resource. Skipping")
        return
    if not hasattr(queue.cfn_resource, KEY):
        return
    queue_encryption = queue.cfn_resource.KmsMasterKeyId
    if isinstance(queue_encryption, str):
        key_parts = queue_encryption.split(r"x-kms::")
        if not key_parts or not key_parts[-1] == kms_key.name:
            return
        assign_kms_key_to_queue(kms_key, queue, queue_stack, settings)
