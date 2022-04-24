
.. meta::
    :description: ECS Compose-X AWS X-Ray syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS X-Ray, tracing, distributed tracing

.. _xray_syntax_reference:

==================
services.x-xray
==================

This section allows to automatically add the ``xray-daemon`` sidecar to your task definition, automatically
defining port, environment variables for the other containers to use.

Syntax reference
=================

.. code-block:: yaml

    x-xray: True/False


Example
=======

.. code-block:: yaml
    :caption: Enable XRay for your service.

    services:
      serviceA:
        x-xray: True

.. seealso::

    ecs_composex.ecs.ecs_service#set_xray

IAM permissions
===============

Enabling XRay will automatically add the following managed policy to your task definition:

**arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess**

.. code-block:: json
    :caption: IAM policy definition

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                    "xray:GetSamplingStatisticSummaries"
                ],
                "Resource": [
                    "*"
                ]
            }
        ]
    }
