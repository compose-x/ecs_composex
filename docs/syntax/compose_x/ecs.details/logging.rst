.. meta::
    :description: ECS Compose-X logging syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CloudWatch, AWS Logs, logging

.. _x_configs_logging_syntax_reference:

=========
x-logging
=========

Presently, ECS Compose-X only caters for using AWS CloudWatch logs driver.
When deploy new services, first a specific log group for that service in the deployment is created and granted access to
via IAM.

The settings below will allow you to configure some of the settings defined in the Container Definition logging definition.

.. code-block:: yaml
    :caption: x-logging syntax definition

    RetentionInDays: int
    CreateLogGroup: bool|str

.. hint::

    Alternatively you can use the ECS Plugin logging definition will ECS Compose-X will use.
    If both are defined, priority goes to Compose-X declaration.

RetentionInDays
=====================

Value to indicate how long should the logs be retained for the service.

.. hint::

    If the value you enter is not in the allowed values, will set to the closest accepted value.


.. hint:: Emulates the CW Logs property `RetentionInDays Property`_

CreateLogGroup
===============

Allows you to define whether or not you want ComposeX to create the LogGroup.
If set to False, it will grant *logs:CreateLogGroup* to the Execution Role.
It will also define in the *awslogs driver* (`awslogs driver documentation`_) and set **awslogs-create-group** to True


Examples
========

.. code-block:: yaml

    services:
      serviceA:
        x-logging:
          CreateLogGroup: True
          RetentionInDays: 30


.. _RetentionInDays Property: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-logs-loggroup.html#cfn-logs-loggroup-retentionindays
.. _awslogs driver documentation: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html
