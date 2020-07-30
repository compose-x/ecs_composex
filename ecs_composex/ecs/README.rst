From docker-compose to AWS ECS
================================

This module is responsible to understanding the docker compose file as a whole and then more specifically putting
together the settings of the services defined.

services
---------

The services are defined in YAML under the `services` section.
Each service then has its own set of properties that can be defined.

.. seealso::

    `Docker Compose file reference`_

x-configs
---------

To enable further configuration and customization in an easy consumable format, still ignored by docker-compose natively,
you can define **x-configs** into the services definitions.

Features that ECS ComposeX takes care of for you, if you needed to:

* Create AWS LoadBalancers, NLB or ALB that route traffic to your applications
* Register services into Service Discovery using AWS Cloud Map
* Adds X-Ray side car when you need distributed tracing
* Calculates the compute requirements based on the docker-compose v3 declaration
* Supports to add IAM permission boundary for extended security precautions.

.. note::

    :ref:`services_syntax_reference`


ECS Cluster configuration
=========================

**x-cluster** allows you to configure the ECS Cluster as you wish to, instead of my own defaults.
If you do not specify your own settings, the default settings will be applied.

Default settings:
-----------------

As you know, I am going for Fargate first and only as the default deployment mechanism.

* FARGATE_SPOT, Weight=4, Base=1
* FARGATE, Weight=1

Setting the Properties accordingly to `AWS CloudFormation Reference for ECS Cluster <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-cluster.html>`_
will allow you to override the default settings with your own.

.. note::

    Head to :ref:`cluster_syntax_reference` for more details on how to use x-cluster.

.. _Docker Compose file reference: https://docs.docker.com/compose/compose-file
