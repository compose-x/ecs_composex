
.. meta::
    :description: ECS Compose-X AWS Kinesis syntax reference
    :keywords: AWS, ECS, firehose

.. _kinesis_syntax_reference:

=====================
x-kinesis_firehose
=====================

.. code-block:: yaml

    x-kinesis_firehose:
      stream-logical-name:
        Properties: {}
        MacroParameters: {}
        Lookup: {}
        Services: {}


Services
=========

.. code-block:: yaml

    x-kinesis_firehose:
      stream-logical-name:
        Services:
          my-app:
            Access: Producer
            ReturnValues: {}

    services:
      my-app: {}

ReturnValues
-------------

The available return values are as defined in `AWS Firehose CloudFormation ReturnValues`_

IAM Permissions
-----------------

The only value for `Access` is **Producer** which allows the clients to publish records to the Delivery Stream.

.. literalinclude:: ../../../ecs_composex/kinesis_firehose/kinesis_firehose_perms.json
    :language: json

Properties
==============

Refer to `AWS::KinesisFirehose::DeliveryStream`_ documentation page for all the properties you can set.
They are all supported, and been tested with slightly modified versions of the examples.

When creating a new Firehose DeliveryStream, ECS Compose-X wil also automatically create a new IAM role that will be
used to grant the service role access to your other AWS Resources, such as S3/Kinesis and others.

See below for information on how to change the behaviour.

Modified properties
-----------------------

The following properties are updated automatically. See `MacroParameters`_ to disable the automatic change of these
properties.

.. _kinesis_firehose_iam_role_autoreplaced:

* KinesisStreamSourceConfiguration.RoleARN
* AmazonopensearchserviceDestinationConfiguration.RoleARN
* S3DestinationConfiguration.RoleARN
* ElasticsearchDestinationConfiguration.RoleARN
* ExtendedS3DestinationConfiguration.RoleARN
* RedshiftDestinationConfiguration.RoleARN


MacroParameters
==================

DoNotOverrideIamRole
-----------------------

This can be either set as a boolean (True|False) or as a list of string, representing the Destination/Source
for which you **do not want ECS Compose-X to replace with a new IAM Role**.

So in the Properties, if you defined ``RoleARN`` for one of these properties, it will be automatically updated and
replaced with a new IAM Role that is managed by ECS Compose-X.

Setting to true or as a list, will disable the replacement for all/for the properties listed.

.. warning::

    This means that IAM polices will not be created to allow the appropriate API calls to work with the other
    ``x-<resource>`` defined in your file.
    Use at your own risks, if you know what you are doing.

.. code-block:: yaml

    x-kinesis_firehose:
      stream-logical-name:
        MacroParameters:
          DoNotOverrideIamRole: true

      another-stream-logical-name:
        MacroParameters:
          DoNotOverrideIamRole:
            - ElasticsearchDestinationConfiguration
            - AmazonopensearchserviceDestinationConfiguration

x-iam
---------

This allows to define additional IAM properties manually.

PermissionsBoundary
^^^^^^^^^^^^^^^^^^^^^

Allows to define a ``PermissionsBoundary`` to link to the IAM Role.
By default, there is none.

Link to other AWS Resources
==============================

.. attention::::

    This is only possible for new Firehose Delivery Streams. Compose-X won't update existing ones
    that weren't under its control.

.. hint::

    ECS Compose-X will automatically update the IAM permissions of the new IAM Role associated with the DeliveryStream

    .. note::

        ECS Compose-X will **NOT** update the IAM Role permissions if you disabled it for the source/destination
        of the delivery stream.

The following resources are supported to be defined in the compose file, and be interpolated with the resource properties

* `S3 Buckets`_ with :ref:`s3_syntax_reference`
* `Kinesis Streams`_ with :ref:`kinesis_syntax_reference`
* `KMS keys`_ with :ref:`kms_syntax_reference`

.. tip::

    Adding OpenSearch is in the to-do list. Feel free to open a Feature Request to see it added with priority.

S3 Buckets
------------

You can use ``x-s3::<bucket-name>`` for the following properties

* S3DestinationConfiguration::`BucketARN`_
* ExtendedS3DestinationConfiguration::`BucketARN`_
* ExtendedS3DestinationConfiguration::S3BackupConfiguration::`BucketARN`_
* RedshiftDestinationConfiguration::S3BackupConfiguration::`BucketARN`_
* ElasticsearchDestinationConfiguration::S3BackupConfiguration::`BucketARN`_
* AmazonopensearchserviceDestinationConfiguration::S3BackupConfiguration::`BucketARN`_
* SplunkDestinationConfiguration::S3BackupConfiguration::`BucketARN`_
* HttpEndpointDestinationConfiguration::S3BackupConfiguration::`BucketARN`_

.. code-block:: yaml
    :caption: Example for S3 Extended configuration

    x-s3:
      delivery-stream-output-bucket:
        Properties: {}

    x-kinesis_firehose:
      stream-to-s3-direct-put:
        Properties:
          DeliveryStreamName: tester-partitioning-delimiter
          DeliveryStreamType: DirectPut
          ExtendedS3DestinationConfiguration:
            BucketARN: x-s3::delivery-stream-output-bucket

It will grant the corresponding IAM permissions to the IAM Role linked to the Firehose DeliveryStream

.. literalinclude:: ../../../ecs_composex/s3/s3_perms.json
    :lines: 161-189
    :language: json



Kinesis Streams
----------------

You can use ``x-kinesis::<stream-logical-name>`` to update the value for `KinesisStreamSourceConfiguration.KinesisStreamARN`_
This will automatically set the right value for it and

It will grant the corresponding IAM permissions to the IAM Role linked to the Firehose DeliveryStream

.. literalinclude:: ../../../ecs_composex/kinesis/kinesis_perms.json
    :lines: 31-44
    :language: json

KMS Keys
----------

This will allow to update the value for `DeliveryStreamEncryptionConfigurationInput.KeyARN`_ and where applicable,
`EncryptionConfiguration.KMSEncryptionConfig.AWSKMSKeyARN`_

Note that if the key is imported via Lookup, it must be a Customer CMK.


It will grant the corresponding IAM permissions to the IAM Role linked to the Firehose DeliveryStream

.. literalinclude:: ../../../ecs_composex/kms/kms_perms.json
    :lines: 46-69
    :language: json


JSON Schema
============

Model
-------

.. jsonschema:: ../../../ecs_composex/kinesis_firehose/x-kinesis_firehose.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/kinesis_firehose/x-kinesis_firehose.spec.json

Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/firehose>`__ to use
as reference for your use-case.

.. _AWS Firehose CloudFormation ReturnValues: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesisfirehose-deliverystream.html#aws-resource-kinesisfirehose-deliverystream-return-values
.. _AWS::KinesisFirehose::DeliveryStream: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesisfirehose-deliverystream.html#aws-resource-kinesisfirehose-deliverystream-properties
.. _BucketARN: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-s3destinationconfiguration.html#cfn-kinesisfirehose-deliverystream-s3destinationconfiguration-bucketarn
.. _KinesisStreamSourceConfiguration.KinesisStreamARN:: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-kinesisstreamsourceconfiguration.html
.. _DeliveryStreamEncryptionConfigurationInput.KeyARN: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-deliverystreamencryptionconfigurationinput.html
.. _EncryptionConfiguration.KMSEncryptionConfig.AWSKMSKeyARN: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-kinesisfirehose-deliverystream-kmsencryptionconfig.html
