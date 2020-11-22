.. _xray_syntax_reference:

=======
x-xray
=======

This section allows to enable X-Ray to run right next to your container.
It will use the AWS original image for X-Ray Daemon and exposes the ports to the task.

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
