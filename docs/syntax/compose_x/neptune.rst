.. meta::
    :description: ECS Compose-X AWS Neptune syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Neptune, MongoDB

.. _neptune_syntax_reference:

==========================
x-neptune
==========================

This modules allows you to provision new AWS Neptune DB Clusters, or use existing ones, that your services will connect to.

.. contents::
    :depth: 2

Definition
============

YAML Representation
----------------------

.. code-block:: yaml
    :caption:

x-neptune:
  cluster-01:
    Properties: {}
    MacroParameters: {}
    Lookup: {}
    Services: {}
    Settings: {}


Define services access
=======================


.. code-block:: yaml

    services:
      frontend: {}
      backend: {}

    x-neptune:
      cluster-01:
        Services:
          backend:
            Access:
              NeptuneDB: <access policy>
              DBCluster: <access policy>
            ReturnValues: {}


.. note::

    AWS Neptune clusters only support AWS IAM authentication to allow users to connect to the cluster nodes.
    Therefore when using Lookup, you need only to specify Tags or Identifier for the cluster, ECS Compose-X will do the rest.


MacroParameters
================

These parameters will allow you to define extra parameters to define your cluster successfully.

.. code-block:: yaml

    Instances: []
    DBClusterParameterGroup: {}

Instances
---------

List of Neptune instances. The aspiration is to follow the same syntax as the `Neptune Instance`_.

.. note::

    Not all Properties are respected, instead, they follow logically the attachment to the Neptune Cluster.


.. code-block:: yaml

    Instances:
      - DBInstanceClass: <db instance type>
        PreferredMaintenanceWindow: <window definition>
        AutoMinorVersionUpgrade: bool

.. hint::

    If you do not define an instance, ECS ComposeX automatically creates a new one with a single node of type **db.t3.medium**

DBClusterParameterGroup
------------------------

See `Neptune DBClusterParameterGroup`_ for full details.

Lookup
========

For Neptune, given that only IAM is required to access the cluster, there is no extra parameter as for x-rds/x-documentdb.
The lookup will automatically deal with finding the Security Group too and allow ingress from your designated services.


Examples
========

.. literalinclude:: ../../../use-cases/neptune/create_only.yml
    :language: yaml
    :caption: Create a new Neptune Cluster

.. literalinclude:: ../../../use-cases/neptune/lookup.yml
    :language: yaml
    :caption: Lookup Neptune DB Cluster


JSON Schema
==========================

Definition
------------

.. jsonschema:: ../../../ecs_composex/specs/x-neptune.spec.json

Literal
--------

.. literalinclude:: ../../../ecs_composex/specs/x-neptune.spec.json


.. _Neptune Cluster properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-neptune-dbcluster.html
.. _Neptune Instance: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-neptune-dbinstance.html
.. _Neptune DBClusterParameterGroup: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-neptune-dbparametergroup.html