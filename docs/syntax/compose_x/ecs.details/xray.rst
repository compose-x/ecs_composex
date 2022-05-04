
.. meta::
    :description: ECS Compose-X AWS X-Ray syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS X-Ray, tracing, distributed tracing

.. _xray_syntax_reference:

==================
services.x-xray
==================

.. code-block:: yaml

    services:
      frontend:
        x-xray: True/False

Automatically add the ``xray-daemon`` sidecar to your task definition, automatically
defining port, environment variables for the other containers to use.


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
