.. meta::
    :description: ECS Compose-X AWS ECS Cluster syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ECS, AWS Fargate, ECS Spot

.. _ecs_cluster_syntax_reference:

==========
x-cluster
==========

.. contents::
    :depth: 2

`JSON Schema Definition <https://github.com/compose-x/ecs_composex_specs/blob/main/ecs_composex_specs/x-cluster.spec.json>`_

Properties
==========
Refer to the `AWS CFN reference for ECS Cluster`_

.. code-block:: yaml
    :caption: Override default settings

    x-cluster:
      Properties:
        CapacityProviders:
          - FARGATE
          - FARGATE_SPOT
        ClusterName: spotalltheway
        DefaultCapacityProviderStrategy:
          - CapacityProvider: FARGATE_SPOT
            Weight: 4
            Base: 2
          - CapacityProvider: FARGATE
            Weight: 1

Lookup
======
Allows you to enter the name of an existing ECS Cluster that you want to deploy your services to.

.. code-block:: yaml
    :caption: Lookup existing cluster example.

    x-cluster:
      Lookup:
        Tags:
          - name: clusterabcd
          - costcentre: lambda


.. warning::

    If the cluster name is not found, by default, a new cluster will be created with the default settings.

Use
===

This key allows you to set a cluster to use, that you do not wish to lookup, you just know the name you want to use.
(Useful for multi-account where you can't lookup cross-account).


.. _AWS CFN reference for ECS Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-cluster.html
