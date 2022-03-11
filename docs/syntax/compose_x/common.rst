.. _common_syntax_reference:

==============================
Common syntax for x-resources
==============================

ECS ComposeX requires to expands onto the original Docker compose file defintion in order to map the docker compose
properties to their equivalent settings on AWS ECS and otherwise for the other "Extra" resources.

In general for each x- section of the docker compose document, we will find three attributes to each resource:

* `Properties`_
* `Settings`_
* `Services`_
* `Lookup`_

.. seealso::

    For more structural details, see `JSON Schema`_


.. _services_ref:

Services
========

This section of the resource declaration allows to designate which services will be allowed access, and how.
We divided resources in different categories:

* API based Resources: AWS service resource that you only require IAM policies in place to access.
* Network based Resources: AWS Services you require network access to, via Security Group rules

To see what IAM Policies are available for these resources, refer to the specific services documentation.

Syntax
---------

.. code-block:: yaml

    services:
      frontend: {}
      backend: {}
      etl: {}

    x-dynamodb: # DynamoDB only requires IAM permissions for access. We provide the name of the policy
      tableA:
        Properties: {}
        Services:
          backend:
            Access: RW # Read / Write access to the table and indexes
          etl:
            Access: RO # Read Only access to the table and indexes
            ReturnValues:
              Arn: TABLE_A_ARN # Here we also expose to the containers the Arn value of the table into a variable TABLE_A_ARN

    x-docdb: # To access DocumentDB, we need to grant network access and IAM permissions to the secret, done automatically
      db-01:
        Services:
          backend:
            Access:
              DBCluster: RO # Here, we grant additional IAM permissions to the service to allow describe of the cluster.
            ReturnValues:
              ClusterResourceId: DB01_CLUSTER_ID # We expose the ClusterResourceId value into a variable DB01_CLUSTER_ID to the service.


.. warning::

    For retro-compatibilty (at the time of 0.18 release) the previous syntax is maintained, but won't support `ReturnValues`_

    .. code-block:: yaml

        services:
          frontend: {}
          backend: {}
          etl: {}

        x-dynamodb:
          tableA:
            Properties: {}
            Services:
              - name: backend:
                access: RW
              - name: etl:
                access: RO

Access
^^^^^^^^

The API based Resources only require the name of the IAM Policy you want to assign to the role.
However, for network related resources, we also need to grant network access via Security Group ingress rules.
ECS Compose-X takes care of that for you, by detecting the Security Group in use by the targeted service, and
creating an Ingress rule.

Furthermore, in order to allow deeper automation on the service side, additional IAM permissions can be granted to the
service, to describe and retrieve properties of the target: this can be very handy to have the service use AWS APIs to
discover endpoints (i.e. Write vs Read-Only endpoints of a RDS Cluster) or simply to monitor the target.

.. tip::

    The security ingress rules to services, such as EFS, RDS etc, are created in the same stack as the ECS Service is.
    The ECS Service depends on permissions before being created / updated.


ReturnValues
^^^^^^^^^^^^^^^

The ReturnValues property allow you to retrieve specific properties and expose the value as an environment variable
to your service. The return value structure is a key/value argument, where the *key* represents the property you want
the value of, i.e. RDS Read Endpoint, DocumentDB/Neptune ClusterResourceId etc. The *value* represents the environment
variable name that will be exposed to your container.


For example, if we take these three resources

.. code-block:: yaml

    x-sqs:
      queue01: # We only set the access, no return values
        Services:
          backend:
            Access: RW

    x-neptune:
      cluster-01:
        Services:
          backend:
            Access:
              Http: RW
              DBCluster: RO
            ReturnValues:
              ClusterResourceId: CLUSTER_ID

      cluster-0002:
        Services:
          backend:
            Access:
              Http: RW
              DBCluster: RO
            ReturnValues:
              DBClusterArn: CLUSTER_ID # Here when specifying the env var to CLUSTER_ID, this will conflict with cluster-01 value.

.. hint::

    There is always one default value returned and exposed to the container, which represents the `Ref` value for the resource.
    In the example above, the SQS Queue URL will be the value exposed to the service, with env variable named **QUEUE01**

.. warning::

    Ensure not to give the same environment variable name to different properties twice: the last one to be processed
    will be the one used for that environment variable.
    In the example above, although we want two different properties from the different resources, the environment variable
    is the same, therefore the value will be wrong for one of them. To avoid that, simply change the environment variable name.

.. _x_resource_service_scaling_def:

Scaling
^^^^^^^^^^^

This allows to define how to implement autoscaling, which uses AWS Application Autoscaling, and in the current implementation
allows to define StepScaling of the containers.

You can create arbitrary alarms of your own, to define scaling based on Metrics and Dimensions.
Some dimensions have a built-in mechanism that allows for you to point to other x-resources (i.e. x-elbv2)
and it would automatically pick up the right name and properties to use.

`StepScaling <https://docs.aws.amazon.com/autoscaling/application/userguide/application-auto-scaling-step-scaling-policies.html>`_ is rather straight forward, and the documentation
explains it very well. Once you defined your alarm, and indicate which services should scale based on it, ECS Compose-X will do
the rest for you.

.. warning::

    If you create different alarms / scaling rules for a same service, the desired count used will be **the highest resolved value**.
    So ensure that your conditions are correct.

.. code-block:: yaml

    Scaling:
      Steps:
        - LowerBound: 0 # From 0
          UpperBound: 1000 # To 1000
          Count: 2 # Deploy 2 containers
        - LowerBound: 1000 # From 1000
          UpperBound: 10000 # To 10000
          Count: 6 # Deploy 2 containers
        - LowerBound: 10000 # From 10000 to infinity
          Count: 12 # Deploy 2 containers


JSON model
"""""""""""""""

.. jsonschema:: ../../../ecs_composex/specs/ingress.spec.json#/definitions/ScalingDefinition


Properties
==========

Unless indicated otherwise, these are the properties for the resource as you would define them using the AWS properties
in the AWS CloudFormation resource definition.

.. warning::

    In order to update some resources, AWS Sometimes needs to create new ones to replace the once already in place,
    depending on the type of property you are changing. To do so, AWS will need to have the name of the resource
    generated, and not set specifically for it. It is a limitation, but in the case of most of the resources, it also
    allows for continued availability of the service to the resources.

    Therefore, some resources will not be using the `Name` value that you give to it, if you did so.

.. _lookup_syntax_reference:

Lookup
======

Allows you to Lookup existing resources (tagged) that you would like to use with the new services you are deploying.
Everything with regards to the access and other properties, depending on the type of resources, will remain the same.

This is accomplished by using **AWS Resources Group Tags API** which means, you can only find resources that are tagged.

.. code-block:: yaml
    :caption: Generic format for Lookup

    Lookup:
      Tags:
        - Key: Value
        - Key: Value
      RoleArn: <str|optional>

.. hint::

    Future versions will add AWS Control API support for lookup.

Tags
------

The tags are a list of Tags that have been assigned to the resource. Based on the type of resource, this might
need to resolve to a single specific resource in your AWS account / region.

RoleArn
--------

This allows you to provide the ARN of an IAM Role that ComposeX can use in order to lookup for resources.
It is very useful in case you plan to do cross-account lookup for shared resources or simply to render
your templates in a central CICD account.

.. note::

    Compose-X will never modify the looked up object!


.. warning::

    You can only lookup tagged resource on AWS.
    The only exception is x-dns which will lookup into Route53 directly.

.. tip::

    Tags keys and values are case sensitive.

.. _settings_syntax_reference:

Settings
========

The settings is the section where we can take shortcuts or wrap around settings which would otherwise be complex to
define. Sometimes, it simply is an easy way to use helpers which are configurable. For example, in the next interation
for the x-rds resources, we will allow to define the latest RDS engine and version that supports Serverless for aurora.

There is a set of settings which are going to be generic to all modules.

.. _common_settings_subnets:


Subnets
-------

.. code-block:: yaml
    :caption: Example of override for RDS

    x-rds:
      dbA:
        Settings:
          Subnets: AppSubnets

This parameter allows you to override which subnets should be used for the resource to be deployed to.
It applies to that resource only so if you had for example, multiple RDS instances, default behaviour is observed for all
resources that do not have this override.

.. note::

    This only applies to services that require to be deployed and communicated with in the AWS VPC.


.. note::

    For ECS services to be deployed into different subnets, refer to :ref:`compose_networks_syntax_reference`


x-cloudmap
-------------

This allows you to register your services into AWS Service Discovery (AWS CloudMap) automatically.

See :ref:`resources_settings_cloudmap` for more details.


JSON Schema
============

Ingress Definition
-----------------------

.. jsonschema:: ../../../ecs_composex/specs/ingress.spec.json

Common specifications for resources
-------------------------------------

.. jsonschema:: ../../../ecs_composex/specs/x-resources.common.spec.json
