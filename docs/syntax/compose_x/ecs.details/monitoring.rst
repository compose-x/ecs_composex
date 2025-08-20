
.. meta::
    :description: ECS Compose-X service level x-monitoring extensions
    :keywords: AWS, AWS ECS, compose, monitoring

.. _x_services_monitoring_syntax:

======================
services.x-monitoring
======================

.. code-block:: yaml

    services:
      serviceA:
        x-monitoring:
          CWAgentCollectEmf: true
          CollectEmf:
            CloudwatchAgent:
              UseLatest: true
              InterpolateWithDigest: false

Shorthands for monitoring features.


.. _monitoring_cw_agent_emf_collection:

CWAgentCollectEmf
===================

Option that automatically add the CW Agent to the task definition and allow EMF Collection.

The ``AWS_EMF_AGENT_ENDPOINT`` environment variable for the other services is automatically set to point to the CW Agent.

A new SSM Parameter is created with the configuration necessary, and exposed to the container as ``CW_CONFIG_CONTENT``

See the `AWS CloudWatch agent & EMF Configuration for details`_ of what's configured under the hood.

boolean value
-------------

When set to true, enables the sidecar using the `latest CloudWatch agent image from AWS ECR Public`_.
When set to false, disables EMF collection entirely.

SidecarConfig
--------------

This configuration allows you to define more options to control the behaviour of the used sidecar image.
You must explicitly set either ``UseLatest`` or `OverrideImage`_

.. code-block:: yaml

    services:
      serviceA:
        x-monitoring:
          CWAgentCollectEmf:
            InterpolateWithDigest: true
            OverrideImage: "public.ecr.aws/cloudwatch-agent/cloudwatch-agent:1.247357.0b252275"
            UseLatest: false

.. hint::

    ``UseLatest`` is the default behaviour when using a boolean.

OverrideImage
^^^^^^^^^^^^^^

.. code-block:: yaml

    services:
      serviceA:
        x-monitoring:
          CWAgentCollectEmf:
            InterpolateWithDigest: false
            OverrideImage: "public.ecr.aws/cloudwatch-agent/cloudwatch-agent:1.247357.0b252275"

.. note::

    We recommend to use the latest image generally speaking

InterpolateWithDigest
^^^^^^^^^^^^^^^^^^^^^^

Automatically enables attempt to resolve the image digest. Uses the :ref:`composex_docker_opts_extension` to resolve
the digest.

.. hint::

    This setting is recommended if you want to ensure that the image used is going to be consistently the same throughout
    the lifecycle of your Task Definition revision.

.. code-block:: yaml

    services:
      serviceA:
        x-monitoring:
          CWAgentCollectEmf:
            InterpolateWithDigest: true
            UseLatest: true

.. _AWS CloudWatch agent & EMF Configuration for details: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Generation_CloudWatch_Agent.html
.. _latest CloudWatch agent image from AWS ECR Public: https://gallery.ecr.aws/cloudwatch-agent/cloudwatch-agent
