.. meta::
    :description: ECS Compose-X AWS Elasticache syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Elasticache, redis, memcached

.. _elastic_cache_syntax_reference:

===================
x-elastic_cache
===================

.. code-block:: yaml
    :caption: syntax reference

    Properties: {}      # AWS CacheCluster or ReplicationGroup properties
    MacroParameters: {} # Shortcut parameters to get going quickly
    Settings: {}        # Generic settings supported by all resources
    Services: []        # List of services that will get automatically access to the resource.
    Lookup: {}          # Lookup definition to find existing Cache or ReplicationGroup.


.. hint::

    ECS ComposeX will always create a new SecurityGroup for a new resource to ensure the services can get access by
    setting EC2 Security Ingress rules.

Properties
==========

This allows you to define all the properties for either the `AWS CacheCluster`_ or `AWS Replication Group`_ resource as
part of the AWS ElasticCache family.

ECS ComposeX will automatically detect which of the two resource it is, based on the properties you will define.


.. note::

    ECS ComposeX evaluates first for CacheCluster, so you might need to add an extra different parameter for ReplicationGroup
    to be detected appropriately.


MacroParameters
===============

This allows you to define a very few of the `AWS CacheCluster`_ resource if you do not want to define the `Properties`_
and / or extra resources that are common to both the ReplicationGroup and CacheCluster.

.. code-block:: yaml
    :caption: Short syntax for properties to create a new CacheCluster

    Engine: "redis|memcached"           # The engine, required.
    EngineVersion: <engine_version>     # The engine version, required
    CacheNodeType: <cache_node type>    # Optionally, define the CacheNodeType, defaults to cache.t3.small
    NumCacheNodes: <N>                  # Optionally, define the NumCacheNodes, defaults to 1
    ParameterGroup: {}                  # Optioanlly, define a new parameter group

ParameterGroup
---------------

This allows you to create a specific parameter group for the CacheCluster or ReplicationGroup.
It supports all of the properties you can set in the original `AWS ParameterGroup`_ definition.

.. hint::

    Your parameter group settings have to match the settings supported by the Engine. Refer to `Engine Parameters guide`_
    to see what the engine you have can support as settings.

Settings
=========

See :ref:`settings_syntax_reference`

Services
=========

.. code-block:: YAML

    Services:
      - name: <service name>    # Service or Family name
        access: <ignored>       # Generic property that has to be set, ignored for now.

List of services you want to grant access to the CacheCluster or ReplicationGroup to.
ECS ComposeX will automatically get the attributes of your cluster based on its type (Memcached/Redis/Redis ReplicationGroup),
and pass these on down to the service stack.

Most importantly, it will create the SecurityGroup Ingress rules to allow your service to have access to the Cluster Node
via the indicated SecurityGroup.

.. hint::

    ECS ComposeX will not handle the Redis6.x RBAC access as this is a lot more involved than generating CFN templates etc.
    This might come in a future version.

Lookup
=======

This allows you to define via Tags the ElasticCache Cluster or ReplicationGroup that already exists and you want your services
to have access to.

It will automatically select the AWS Security Group associated with your cluster and put down the settings of your cluster into a
CloudFormation mapping to pass it onto the services.

Examples
=========

.. literalinclude:: ../../../use-cases/elasticache/create_only.yml
    :language: YAML


.. _AWS CacheCluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticache-cache-cluster.html
.. _AWS Replication Group: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticache-replicationgroup.html
.. _AWS ParameterGroup: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticache-parameter-group.html
.. _Engine Parameters guide: https://docs.aws.amazon.com/AmazonElastiCache/latest/red-ug/ParameterGroups.html
