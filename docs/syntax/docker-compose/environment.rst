
.. _environment_syntax_reference:

===================
environment
===================

Environment variables play a crucial role in configuring the services.
You can define environment variables to set properties from resources or AWS Intrinsic functions.

For example, you can do

.. code-block:: yaml

    services:
      web-server:
        environment:
          ENV_VAR: value_01
          SIMPLE_PROPERTY: x-s3::storage-bucket::BucketName
          AWS_REGION: x-aws::AWS::Region
          COMPLEX_ENV_VAR: s3://x-s3::storage-bucket::BucketName/x-aws::AWS::Provider/cluster_01

    x-s3:
      storage-bucket:
        Lookup:
          Tags:
            Name: my-docs

* SIMPLE_PROPERTY will resolve into the value of the BucketName. We assume the bucket name is ``my-docs``
* AWS_REGION will result to the AWS Region the AWS Stack is deployed in.
* COMPLEX_ENV_VAR will result in ``s3://my-docs/eu-west-1/cluster_01``
