
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
          CWAgentCollectEmf: bool

Shorthands for monitoring features.


.. _monitoring_cw_agent_emf_collection:

CWAgentCollectEmf
===================

Simple boolean that will automatically add the CW Agent to the task definition and allow EMF Collection.
The ``AWS_EMF_AGENT_ENDPOINT`` environment variable for the other services is automatically set to point to the CW Agent.
A new SSM Parameter is created with the configuration necessary, and exposed to the container as ``CW_CONFIG_CONTENT``

See the `AWS CloudWatch agent & EMF Configuration for details`_ of what's configured under the hood.

.. _AWS CloudWatch agent & EMF Configuration for details: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Generation_CloudWatch_Agent.html
