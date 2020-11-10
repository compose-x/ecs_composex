.. _kms_syntax_reference:

======
x-kms
======

Syntax
=======

.. code-block:: yaml

    x-kms:
      keyA:
        Properties: {}
        Settings: {}
        Services: []
        Lookup: {}

Properties
==========

See `AWS CFN KMS Key Documentation`_

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

Settings
========


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


.. _AWS CFN KMS Key Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kms-key.html
