.. meta::
    :description: ECS Compose-X AWS Kinesis syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Kinesis, kinesis, datastream

.. _kinesis_syntax_reference:

===========
x-kinesis
===========

This module helps you create new Kinesis Data Streams supporting all the AWS CFN properties and link these streams to your
services.

Syntax reference
==================

.. code-block:: yaml
    :caption: x-kinesis Syntax reference

    x-kinesis:
      stream:
        Properties: {} # AWS Kinesis CFN definition
        Settings: {}
        MacroParameters: {}
        Services: []


Properties
===========

The Properties are the `AWS CFN definition for AWS Kinesis streams`_.


MacroParameters
================

No specific MacroParameters for Kinesis data streams. Given the AWS definition is very straightforward, just define the properties.
The only truly required property is the `ShardCount`_

Settings
=========

The settings are as usual, allow you to define `EnvNames`_

EnvNames
---------

List of String that allow you to define multiple environment names for the stream to be exposed to your service.
Value for these is the **AWS Kinesis Stream name** (Default value returned by Fn::Ref


Services
=========

As per the generic Services definition, we have a list of object, name and access, which define how the service can access the stream.

For AWS Kinesis streams, we have the following permissions.

* Producer
* Consumer
* PowerUser


Examples
==========

.. code-block:: yaml
    :caption: Services definition example

    services: [serviceA, serviceB]

    x-kinesis:
      streamA:
        Properties:
          ShardCount: 2
        Services:
          - name: serviceA
            access: Producer
          - name: serviceB
            access: Consumer


IAM permissions
================

.. literalinclude:: ../../../ecs_composex/kinesis/kinesis_perms.json
    :language: JSON
    :caption: IAM permissions pre-defined for your services.


.. _AWS Kinesis page: https://aws.amazon.com/kinesis/
.. _AWS CFN definition for AWS Kinesis streams: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesis-stream.html
.. _ShardCount: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesis-stream.html#cfn-kinesis-stream-shardcount
