.. _x_configs_logging_syntax_reference:

=========
x-logging
=========

.. contents::

Section to allow passing in arguments for logging.

RetentionInDays
=====================

Value to indicate how long should the logs be retained for the service.

.. note::

    If the value you enter is not in the allowed values, will set to the closest accepted value.


.. hint:: Emulates the CW Logs property `RetentionInDays Property`_



CreateLogGroup
===============

Allows you to define whether or not you want ComposeX to create the LogGroup.
If set to False, it will grant *logs:CreateLogGroup* to the Execution Role.
It will also define in the *awslogs driver* (`awslogs driver documentation`_) and set **awslogs-create-group** to True


.. _RetentionInDays Property: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-logs-loggroup.html#cfn-logs-loggroup-retentionindays
.. _awslogs driver documentation: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html
