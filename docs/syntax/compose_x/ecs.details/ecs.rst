.. meta::
    :description: ECS Compose-X ECS extension
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, security, capacity providers, run-command

.. _composex_ecs_extension:


==================
services.x-ecs
==================

This service level extension will allow to set some of the ECS Service properties

Syntax Reference
==================

.. code-block::

    services:
      serviceA:
        image: nginx/nginx
        x-ecs:
          CapacityProviderStrategy: [CapacityProviderStrategyItem]


.. seealso::

    * `JSON Schema`_
    * `CapacityProviderStrategyItem`_ on AWS official documentation

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/ecs>`__ to use
    as reference for your use-case.


CapacityProviderStrategy
=========================

List of `CapacityProviderStrategyItem`_ that allows to define the CapacityProviders you wish to use for this service,
that comes as an override of the Cluster defined default CapacityProviderStrategy.

.. warning::

    The CapacityProvider defined in the list must be a defined capacity provider in the ECS Cluster.

.. hint::

    When using x-cluster.Lookup, the cluster properties will be evaluated to identify what capacity providers are
    defined on the cluster.

    When assigning the capacity provider to the services, ECS Compose-X **will ensure (fail)**
    that the Capacity Providers defined in x-ecs are present in the ECS Cluster.

    If the cluster has no Capacity Provider defined, validation is skipped.

.. attention::

    When using x-cluster.Use, no validation is performed on the cluster to evaluate available capacity providers.

Examples
=========

.. code-block:: yaml
    :caption: Simple service definition

    services:
      grafana:
        x-ecs:
          CapacityProviderStrategy:
            - CapacityProvider: FARGATE
              Base: 1
              Weight: 2
            - CapacityProvider: FARGATE_SPOT
              Base: 4
              Weight: 8


.. code-block:: yaml
    :caption: Merged definitions

    services:
      grafana:
        deploy:
          labels:
            ecs.task.family: grafana
        x-ecs:
          CapacityProviderStrategy:
            - CapacityProvider: FARGATE
              Base: 1
              Weight: 2
      nginx:
        deploy:
          labels:
            ecs.task.family: grafana
        x-ecs:
          CapacityProviderStrategy:
            - CapacityProvider: FARGATE
              Base: 0
              Weight: 3
            - CapacityProvider: FARGATE_SPOT
              Base: 4
              Weight: 8

In the above example, where grafana and nginx are part of the same task definition and therefore same ECS Service,
we do the following:

* If a capacity provider is set in only one service, we use it for both as-is
* If they both define properties for a same CapacityProvider, here, FARGATE, we take the maximum value of the set.
    Here we take 1 for Base (from grafana) and 3 for Weight (from nginx).


.. _CapacityProviderStrategyItem: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-capacityproviderstrategyitem.html
.. _JSON Schema: https://ecs-composex-specs.compose-x.io/schemas_docs/services/x_ecs.html
