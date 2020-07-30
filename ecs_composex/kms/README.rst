AWS KMS
=======

This python subpackage is responsible for creating the KMS Keys.

Properties
-----------

As for all resources in ECS ComposeX, this section is here to represent the AWS CloudFormation properties you would
normally use to define all the settings.

.. hint::

    All current KMS Key properties are supported. This feature was tested from copy-pasting the AWS examples.

.. seealso::

    `AWS CFN KMS Key Documentation`_

IAM Access types
-----------------

Three access types have been created for the table:

* EncryptDecrypt
* EncryptOnly
* DecryptOnly
* SQS


EncryptDecrypt
^^^^^^^^^^^^^^^^^^^

This allows the micro service read and write access to the table items.

.. code-block:: json
    :caption: Read/Write policy statement snippet

    {
        "Action": [
            "kms:Encrypt",
            "kms:Decrypt",
            "kms:ReEncrypt*",
            "kms:GenerateDataKey*",
            "kms:CreateGrant",
            "kms:DescribeKey",
        ],
        "Effect": "Allow",
    }

EncryptOnly
^^^^^^^^^^^^^^^^^^^

This only allows to query information out of the table items.

.. code-block:: json
    :caption: Encrypt Only.

    {
        "Action": ["kms:Encrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*"],
        "Effect": "Allow",
    }

DecryptOnly
^^^^^^^^^^^

This allows to use the KMS Key to decrypt data.

.. code-block:: json
    :caption: Decrypt Only snippet

    {"Action": ["kms:Decrypt"], "Effect": "Allow"}

SQS
^^^^^^^^^^^

This allows all API calls apart from create and delete the table.

.. code-block:: json
    :caption: SQS Decrypt messages

    {"Action": ["kms:GenerateDataKey", "kms:Decrypt"], "Effect": "Allow"}

.. _AWS CFN KMS Key Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kms-key.html
