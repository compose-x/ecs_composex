.. meta::
    :description: ECS Compose-X AWS KMS syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS KMS, encryption

.. _kms_syntax_reference:

=================
x-kms
=================

This module allows you to specify new and existing KMS Keys you wish to either grant access to your services, or,
link to your other AWS Resources (such as S3, SQS etc.) which would also automatically grant permission to services
accessing these.

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/kms>`__ to use
    as reference for your use-case.

Properties
==========

See `AWS CFN KMS Key Documentation`_

MacroParameters
==================

Alias
------

In addition to EnvNames, for KMS, we also have **Alias** which will create an Alias along with the KMS Key.
The alias name must be a string, not starting with alias/aws or aws. If you specify a an alias starting with **alias/**
then the string will be used as is, if you only specify a short name, then the alias will be prefixed with the RootStack
name and region.

Examples
========

.. code-block:: yaml
    :caption: Simple key creation and link to services

    x-kms:
      keyA:
        Properties:
          PendingWindowInDays: 14
        Services:
          - name: serviceA
            access: EncryptDecrypt
          - name: serviceB
            access: EncryptDecrypt
        Settings:
          Alias: keyA

Services
========

List of key/pair values, as for other ECS ComposeX x-resources.

Three access types have been created for the table:

* EncryptDecrypt
* EncryptOnly
* DecryptOnly
* SQS

.. code-block:: yaml
    :caption: KMS and Services

    x-kms:
      keyA:
        Properties: {}
        Services:
          - name: serviceA
            access: EncryptDecrypt
          - name: serviceB
            access: DecryptOnly

Access
---------

Here are pre-defined IAM permissions to use for your KMS Key.

* EncryptDecrypt
* EncryptOnly
* DecryptOnly
* SQS


.. literalinclude:: ../../../ecs_composex/kms/kms_perms.json
    :language: json
    :caption: KMS Permissions skeleton


ReturnValues
--------------

`See the AWS KMS Key return values from AWS CFN Documentation`_. The value for **Ref** can be accessed with **KeyId**

JSON Schema
============

Representation
-------------------

.. jsonschema:: ../../../ecs_composex/specs/x-kms.spec.json

Definition
-------------

.. literalinclude:: ../../../ecs_composex/specs/x-kms.spec.json
    :language: json


.. _AWS CFN KMS Key Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kms-key.html
.. _See the AWS KMS Key return values from AWS CFN Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kms-key.html#aws-resource-kms-key-return-values
