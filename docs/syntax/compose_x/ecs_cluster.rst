
.. meta::
    :description: ECS Compose-X AWS ECS Cluster syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ECS, AWS Fargate, ECS Spot

.. _ecs_cluster_syntax_reference:

==========
x-cluster
==========

Allows to create / lookup an ECS cluster that will be used to deploy services into.

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


.. _AWS CFN reference for ECS Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ecs-cluster.html

JSON Schema
=============

Model
--------

.. jsonschema:: ../../../ecs_composex/specs/x-cluster.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/specs/x-cluster.spec.json
