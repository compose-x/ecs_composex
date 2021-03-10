﻿.. _syntax_reference:

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

This is accomplished by using AWS Resources Group Tags API which means, at this point in time, you can only find resources
that are tagged.

.. code-block:: yaml
    :caption: Generic format for Lookup

    Lookup:
      Tags:
        - Key: Value
        - Key: Value
      RoleArn: <str|optional>

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

    It will never modify the looked up object!


.. warning::

    You can only lookup tagged resource on AWS.

.. tip::

    Tags keys and values are case sensitive. At this stage, this does not support regexps.

.. _settings_syntax_reference:

Settings
========

The settings is the section where we can take shortcuts or wrap around settings which would otherwise be complex to
define. Sometimes, it simply is an easy way to use helpers which are configurable. For example, in the next interation
for the x-rds resources, we will allow to define the latest RDS engine and version that supports Serverless for aurora.

There is a set of settings which are going to be generic to all modules.

EnvNames
--------
Multiple teams who would want to adopt ECS ComposeX might already have their own environment variable keys (or names)
for a common resource. For example, team A and team B can use the same SQS queue but they did not define a common name
for it, so team A calls it *QueueA* and team B calls it *QUEUE_A*.

With EnvNames, you can define a list of environment variables that will all share the same value, simply have a different
name.

.. hint::

    No need to add the name of the resource as defined in the docker compose file, this will always be added by default.

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

    This only applies to services using TCP, so
    * x-rds
    * x-docdb
    * x-elasticache


.. note::

    For ECS services to be deployed into different subnets, refer to :ref:`compose_networks_syntax_reference`

Services
========

This is a list of object, with two keys: name, access. The name points to the service as defined in the docker compose
file.

.. warning::

    This is case sensitive and so the name of the service in the list must be the same name as the service defined.

.. note::

    At this point in time, each x- section has its own pre-defined IAM permissions for services that support IAM access
    to the resources. In a future version, I might add a configuration file to override that behaviour.

Refer to each x- resource syntax to see which access types are available.
