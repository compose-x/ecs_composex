.. meta::
    :description: ECS Compose-X logging syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CloudWatch, AWS Logs, logging

.. _x_configs_logging_syntax_reference:

=========
x-logging
=========

The following parameter is identical in behaviour to **x-aws-logs_retention** defined in the docker ECS Plugin.

.. code-block:: yaml
    :caption: x-logging syntax definition

    RetentionInDays: int

.. hint::

    Alternatively you can use the ECS Plugin logging definition will ECS Compose-X will use.
    If both are defined, priority goes to the highest value.

RetentionInDays
=====================

Value to indicate how long should the logs be retained for the service.

.. hint::

    If the value you enter is not in the allowed values, will set to the closest accepted value.


.. hint:: Emulates the CW Logs property `RetentionInDays Property`_


Examples
========

.. code-block:: yaml

    services:
      serviceA:
        x-logging:
          RetentionInDays: 42


.. _RetentionInDays Property: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-logs-loggroup.html#cfn-logs-loggroup-retentionindays
