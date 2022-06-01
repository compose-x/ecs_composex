
.. meta::
    :description: ECS Compose-X logging syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CloudWatch, AWS Logs, logging

.. _x_configs_logging_syntax_reference:

======================
services.x-logging
======================

.. code-block:: yaml
    :caption: x-logging syntax definition

    services:
      serviceA:
        x-logging:
          RetentionInDays: int

RetentionInDays
-----------------

Value to indicate how long should the logs be retained for the service.

.. hint::

    If the value you enter is not in the allowed values, will set to the closest accepted value.


.. hint:: Emulates the CW Logs property `RetentionInDays Property`_


FireLens
=========

.. code-block:: yaml

FireLens is a configuration that will automatically generate the configuration for `FluentBit`_ to ship logs in the
appropriate destinations configured.

We recommend the `Rendered`_ configuration which works for AWS Fargate, EC2 and ECS Anywhere.

Rendered
-------------

.. hint::

    We recommend to use that option as it will work in all compute platforms.

s3FileConfiguration
====================

.. note::

    Only works when deploying to AWS ECS on EC2 instances.

Examples
========

.. code-block:: yaml

    services:
      serviceA:
        x-logging:
          RetentionInDays: 42

.. hint::

    The following parameter is identical in behaviour to **x-aws-logs_retention** defined in the docker ECS Plugin.


.. note::

    Alternatively you can use the ECS Plugin logging definition will ECS Compose-X will use.
    If both are defined, priority goes to the highest value.


JSON Schema
===========

Model
--------

.. jsonschema:: ../../../../ecs_composex/specs/services.x-logging.spec.json

Definition
-----------

.. literalinclude:: ../../../../ecs_composex/specs/services.x-logging.spec.json
    :language: json

.. _RetentionInDays Property: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-logs-loggroup.html#cfn-logs-loggroup-retentionindays
.. _FluentBit: https://docs.fluentbit.io/
