
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
        x-xray: true

Automatically add the ``xray-daemon`` sidecar to your task definition, automatically
defining port, environment variables for the other containers to use.

You can set this to either a boolean value or an object to customize the X-Ray daemon configuration.

Boolean Usage
=============

.. code-block:: yaml

    services:
      frontend:
        x-xray: true  # Enable with default settings

      backend:
        x-xray: false  # Disable X-Ray

Object Usage
============

.. code-block:: yaml

    services:
      frontend:
        x-xray:
          OverrideImage: "public.ecr.aws/xray/aws-xray-daemon:3.3.7"


OverrideImage
=============

When using the object format, you can specify a custom X-Ray daemon image instead of using the default AWS-provided image.

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
