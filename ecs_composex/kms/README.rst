.. _aws_kms_readme:

=======
AWS KMS
=======

.. hint::

    All current KMS Key properties are supported. This feature was tested from copy-pasting the AWS examples.

.. seealso::

    `AWS CFN KMS Key Documentation`_

IAM Access types
================

Three access types have been created for the table:

* EncryptDecrypt
* EncryptOnly
* DecryptOnly
* SQS


.. literalinclude:: ../../ecs_composex/kms/kms_perms.json
    :language: json
    :caption: KMS Permissions scaffold


.. _AWS CFN KMS Key Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kms-key.html
