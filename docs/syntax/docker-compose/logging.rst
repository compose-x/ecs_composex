.. _compose_logging_syntax_reference:

============
logging
============

In AWS ECS you can define the log driver in a similar way as you do locally.
In ECS Compose-X, default settings will be applied and use `awslogs driver`_ by default.

For more information on the docker-compose logging syntax, refer to `Docker Compose logging syntax reference`_

Supported drivers
==================

Currently, any other driver is ignored and AWS Logs is used by default. This is to guarantee deployment success on
AWS ECS with AWS Fargate.

awslogs
---------

+---------------------------+----------+-------------------------------------+
| Option Name               | Required | Notes/Features                      |
+===========================+==========+=====================================+
| awslogs-create-group      | False    | Compose-X creates a new             |
|                           |          | log group by default                |
+---------------------------+----------+-------------------------------------+
| awslogs-region            | True     | When specified, Compose-X           |
|                           |          | only handles IAM to grant.          |
|                           |          |                                     |
|                           |          |                                     |
|                           |          | If not set, defaults to AWS::Region |
+---------------------------+----------+-------------------------------------+
| awslogs-endpoint          | False    |                                     |
+---------------------------+----------+-------------------------------------+
| awslogs-group             | True     | Defaults to family name when unset  |
+---------------------------+----------+-------------------------------------+
| awslogs-stream-prefix     | True     | Defaults to service name when unset |
+---------------------------+----------+-------------------------------------+
| awslogs-datetime-format   | False    |                                     |
+---------------------------+----------+-------------------------------------+
| awslogs-multiline-pattern | False    |                                     |
+---------------------------+----------+-------------------------------------+
| mode                      | False    |                                     |
+---------------------------+----------+-------------------------------------+
| max-buffer-size           | False    |                                     |
+---------------------------+----------+-------------------------------------+


.. hint::

    To set the log retention period, you can use :ref:`x_configs_logging_syntax_reference` or **x-aws-logs_retention**

.. _Docker Compose logging syntax reference: https://docs.docker.com/compose/compose-file/compose-file-v3/#logging
.. _awslogs driver: https://docs.aws.amazon.com/AmazonECS/latest/userguide/using_awslogs.html
