
.. meta::
    :description: ECS Compose-X AWS ECS Cluster syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ECS, AWS Fargate, ECS Spot

.. _ecs_cluster_syntax_reference:

==========
x-cluster
==========

Allows to create / lookup an ECS cluster that will be used to deploy services into.

.. attention::

    We highly recommend for production workloads to create the ECS Cluster outside of ECS Compose-X and use the `Lookup`_
    feature.


Properties
==========
Refer to the `AWS CFN reference for ECS Cluster`_

.. code-block:: yaml
    :caption: Override default settings

    x-cluster:
      Properties:
        CapacityProviders:
          - FARGATE
          - FARGATE_SPOT
        ClusterName: spotalltheway
        DefaultCapacityProviderStrategy:
          - CapacityProvider: FARGATE_SPOT
            Weight: 4
            Base: 2
          - CapacityProvider: FARGATE
            Weight: 1

Lookup
======
Allows you to enter the name of an existing ECS Cluster that you want to deploy your services to.

.. code-block:: yaml
    :caption: Lookup existing cluster example.

    x-cluster:
      Lookup:
        Tags:
          - name: clusterabcd
          - costcentre: lambda


.. warning::

    If the cluster name is not found, by default, a new cluster will be created with the default settings.


.. _AWS CFN reference for ECS Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-cluster.html

Secure your cluster and ECS Execution commands
==================================================

With the release of the ECS Execute Command feature, comes the need to implement logging to trace and track who and what
commands are executed remotely. The ECS Cluster Properties allow for you to define S3 Bucket, CW Logs and KMS Key to use
in order to encrypt remote execution and log activities. However, these settings can be tricky to setup for someone new
to AWS.

Enable it with new KMS key, S3 bucket and log group.
-----------------------------------------------------

So to simplify that, we implemented some parameters that will allow you to enable these automatically.

.. code-block:: yaml

    MacroParameters:
      CreateExecLoggingKmsKey: bool
      AllowKmsKeyReuse: bool
      CreateExecLoggingBucket: bool
      CreateExecLoggingLogGroup: bool


CreateExecLoggingKmsKey
+++++++++++++++++++++++++

Will create a new KMS key that will be used to encrypt the execution and its logs.

AllowKmsKeyReuse
+++++++++++++++++++++++++

Only valid if `CreateExecLoggingKmsKey`_ is set to ``True``, this will change the KMS Key policy to allow more service
and IAM resources in the account to use the KMS key, which therefore can be re-used with other ECS Clusters.

CreateExecLoggingBucket
+++++++++++++++++++++++++

Will create a new S3 bucket to store the ECS Execute command logs into. If a KMS key is set (or `CreateExecLoggingKmsKey` ``True``)
it will use that to encrypt the bucket with.

CreateExecLoggingLogGroup
+++++++++++++++++++++++++

Similar to `CreateExecLoggingBucket`_ but this time, for a CloudWatch log group. This might allow you to parse commands
in real-time and detect rogue executions or dangerous ones.

Enable it using existing resources
------------------------------------

.. warning::

    If you are using existing resources that use KMS key, it is your responsibility to ensure the key policy is set
    correctly.

.. code-block:: yaml
    :caption: Override default settings

    x-cluster:
      Properties:
        Configuration:
          ExecuteCommandConfiguration:
            KmsKeyId: x-kms::<key, i.e. existing-key>
            LogConfiguration:
                  CloudWatchEncryptionEnabled: boolean (True (if KmsKeyId is set))
                  CloudWatchLogGroupName: String
                  S3BucketName: String # x-s3::<bucket, i.e logging-bucket> to use an existing bucket
                  S3EncryptionEnabled: boolean # (True (if KmsKeyId is set))
                  S3KeyPrefix: String # Set to whatever value
            Logging: OVERRIDE

    x-s3:
      logging-bucket:
        Lookup: {}

    x-kms:
      existing-key:
        Lookup: {}

When using x-cluster.Lookup
----------------------------

When using x-cluster.Lookup, all of these settings will be automatically detected and the appropriate permissions will
be automatically created.

JSON Schema
=============

Model
--------

.. jsonschema:: ../../../ecs_composex/specs/x-cluster.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/specs/x-cluster.spec.json
