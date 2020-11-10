.. _aws_s3_readme:

=======
AWS S3
=======

This package is here to integrate AWS S3 buckets creation and association to ECS Services.

.. tip::

    For more details on the syntax, head to :ref:`s3_syntax_reference`.

Constraints
===========

S3 buckets are a delicate resource, mostly due to

* Bucket names are within a global domain space, meaning, their can only be one bucket if a given name across all of AWS
* IAM permissions for buckets require to differentiate permissions to the bucket and to the objects
* Buckets also have policies, but we can't add a statement to the policy, one need to update the whole policy with the new statement


Settings
========

AWS S3 bucket properties can be long and tedious to set correctly. To help with making your life easy, additional settings
have been added to shorten the bucket definition.

* ExpandRegionToBucket
* ExpandAccountIdToBucket
* EnableEncryption

.. _s3_access_types_reference:

Access types
============

For S3 buckets, the access types is expecting a object with **objects** and **bucket** to distinguish permissions for each.
If you indicate a string, the default permissions (bucket: ListOnly and objects: RW) will be applied.

.. literalinclude:: ../../ecs_composex/s3/s3_perms.json
    :caption: Full access types policies definitions
    :language: json


Features
========

By default, if not specified, we have decided to encrypt files at rest with **AES256** SSEAlgorithm. The reason for that
choice is that, files are encrypted, for compliance, but without the complexity that KMS can bring and developers can
easily forget about.

Also, objects are not locked, but, all public access is denied by default. You can obviously override these properties.

Lookup
======

.. hint::

    If your bucket is encrypted with a KMS key, the IAM task role for your service is also granted access to that Key
    to manipulate the data in the bucket.
