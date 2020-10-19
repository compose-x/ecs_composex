AWS S3
=======

This package is here to integrate AWS S3 buckets creation and association to ECS Services.

Constraints
-----------

S3 buckets are a delicate resource, mostly due to

* Bucket names are within a global domain space, meaning, their can only be one bucket if a given name across all of AWS
* IAM permissions for buckets require to differentiate permissions to the bucket and to the objects
* Buckets also have policies, but we can't add a statement to the policy, one need to update the whole policy with the new statement


Settings
--------

AWS S3 bucket properties can be long and tedious to set correctly. To help with making your life easy, additional settings
have been added to shorten the bucket definition.

* ExpandRegionToBucket
* ExpandAccountIdToBucket
* EnableEncryption

Services
--------

The services work as usual, with a change syntax for the access, expecting a dictionary to distinguish Bucket and Objects
access, in order to provide the most tuned access to your services.


Features
--------

By default, if not specified, we have decided to encrypt files at rest with **AES256** SSEAlgorithm. The reason for that
choice is that, files are encrypted, for compliance, but without the complexity that KMS can bring and developers can
easily forget about.

Also, objects are not locked, but, all public access is denied by default. You can obviously override these properties.

Lookup
------

As for most resources now, you can lookup and find existing S3 buckets that you wish to manage outside of ComposeX.
So you can set tags to find your bucket (and its name, in which case it will cross-validate it).

.. hint::

    If your bucket is encrypted with a KMS key, the IAM task role for your service is also granted access to that Key
    to manipulate the data in the bucket.

.. tip::

    For more details on the Settings and properties to set in your YAML Compose file,  go to :ref:`s3_syntax_reference`
