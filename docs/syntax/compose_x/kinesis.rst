.. meta::
    :description: ECS Compose-X AWS Kinesis syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Kinesis, kinesis, datastream

.. _kinesis_syntax_reference:

===========
x-kinesis
===========

This module allows you to define Kinesis Data Streams, new or existing ones, that you wish your services to consume/produce
from/to.

Syntax reference
==================

.. code-block:: yaml

    x-kinesis:
      stream:
        Properties: {} # AWS Kinesis CFN definition
        Settings: {}
        MacroParameters: {}
        Services: {}

.. tip::

    You can find the test files for Kinesis `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/kinesis>`__ to use
    as reference for your use-case.


Services
=========

As per the generic Services definition, we have a list of object, name and access, which define how the service can access the stream.

For AWS Kinesis streams, we have the following permissions.


IAM permissions
-----------------

The following predefined permissions are available (see JSON definition of the IAM policy statement below).

* Producer
* Consumer
* PowerUser


.. literalinclude:: ../../../ecs_composex/kinesis/kinesis_perms.json
    :language: JSON
    :caption: IAM permissions pre-defined for your services.

ReturnValues
-------------

To access the **Ref** value, use *StreamId*

See `AWS CFN Kinesis Return Values`_ for available values.

Properties
===========

The Properties are the `AWS CFN definition for AWS Kinesis streams`_.

.. hint::

    If you leave the Properties empty, default values are used and ShardCount is set to 1.

MacroParameters
================

No specific MacroParameters for Kinesis data streams. Given the AWS definition is very straightforward, just define the properties.
The only truly required property is the `ShardCount`_


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


JSON Schema
============

.. jsonschema:: ../../../ecs_composex/specs/x-kinesis.spec.json

.. literalinclude:: ../../../ecs_composex/specs/x-kinesis.spec.json


.. _AWS Kinesis page: https://aws.amazon.com/kinesis/
.. _AWS CFN definition for AWS Kinesis streams: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesis-stream.html
.. _AWS CFN Kinesis Return Values: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesis-stream.html#aws-resource-kinesis-stream-return-values
.. _ShardCount: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-kinesis-stream.html#cfn-kinesis-stream-shardcount
