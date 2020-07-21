From docker-compose to AWS ECS
==============================

This module is responsible to understanding the docker compose file as a whole and then more specifically putting
together the settings of the services defined.

services
---------

The services are defined in YAML under the `services` section.
Each service then has its own set of properties that can be defined.

.. seealso::

    `Docker Compose file reference`_

.. _Docker Compose file reference: https://docs.docker.com/compose/compose-file

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

.. seealso::

    :ref:`services_syntax_reference`
