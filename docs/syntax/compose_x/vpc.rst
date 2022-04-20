
.. meta::
    :description: ECS Compose-X AWS VPC syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS VPC, networking, private network

.. _vpc_syntax_reference:

============================
x-vpc
============================

Allows you to create / lookup an AWS VPC to deploy your services into. When using :ref:`lookup_syntax_reference`, you simply
identify the VPC and the subnets you then place the services and AWS Resources into.

If ``x-vpc`` is not specified, ECS Compose-X will try to figure out whether a new VPC should be created for the given services.
For instance, if using ECS Anywhere and have no services in AWS VPC, the VPC won't be created.

Syntax
================

.. code-block:: yaml

    x-vpc:
      Properties: {}
      Lookup: {}

Properties
============

.. code-block::
    :caption: Create example with a single NAT and 3 VPC Endpoints

    x-vpc:
      Properties:
        SingleNat: true
        VpcCidr: 172.6.7.42/24
        Endpoints:
          AwsServices:
            - service: s3
            - service: ecr.api
            - service: ecr.dkr

VpcCidr
--------------------

The CIDR you want to use.
Default is **100.127.254.0/24**.


SingleNat
--------------------

Whether you want to have 1 NAT per AZ for your application subnets.
Reduces the costs for dev environments!


Endpoints
--------------------

List of VPC Endpoints from AWS Services you want to create.
Default will create Endpoints for ECR (DKR and API).

EnableFlowLogs
^^^^^^^^^^^^^^^^^^^^^^^^^

Whether you want to have a VPC Flow Log created for the VPC.
It will create a new LogGroup and IAM Role to allow logging to CloudWatch.

FlowLogsRoleBoundary
^^^^^^^^^^^^^^^^^^^^^^^^^

For those of you who require IAM PermissionsBoundary for your IAM Roles, this allows to set the boundary.
If it starts with **arn:aws** it will assume this is a valid ARN, otherwise, it will use the value as
policy name.

Lookup
======

.. code-block:: yaml

    x-vpc:
      Lookup:
        VpcId:
          Tags:
            - key: value
        PublicSubnets:
          Tags:
            - vpc::usage: public
        AppSubnets:
          Tags:
            - vpc::usage: application
        StorageSubnets:
          Tags:
            - vpc::usage: storage0



.. warning::

    When using **Use** or **Lookup** you MUST define all 4 settings:
    * VpcId
    * StorageSubnets
    * AppSubnets
    * PublicSubnets


.. warning::

    When creating newly defined subnets groups, the name must be in the format **^[a-zA-Z0-9]+$**


.. hint::

    You can define extra subnet groups based on different tags and map them to your services for override when using
    **Lookup** or **Use**

    .. code-block:: yaml
        :caption: Extra subnets definition

        x-vpc:
          Lookup:
            VpcId: {}
            AppSubnets: {}
            StorageSubnets: {}
            PublicSubnets: {}
            Custom01:
              Tags: {}

        networks:
          custom01:
            x-vpc: Custom01


        services:
          serviceA:
            networks:
              - custom01


.. _vpc_network_design:

Default VPC Network design
==========================


The design of the VPC generated is very simple 3-tiers:

* Public subnets, 1/4 of the available IPs of the VPC CIDR Range
* Storage subnets, 1/4 of the available IPs of the VPC CIDR Range
* Application subnets, 1/2 of the available IPs of the VPC CIDR Range

Default range
-------------

The default CIDR range for the VPC is **100.127.254.0/24**
This leaves a just under 120 IP address for the EC2 hosts and/or Docker containers.

.. hint::

    The range can be changed via **VpcCidr** but not the structure detailed above.
    Works for all RFC 1918 and the 100.64.0.0/10 ranges.

JSON Schema
============

Model
---------------

.. jsonschema:: ../../../ecs_composex/vpc/x-vpc.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/vpc/x-vpc.spec.json
    :language: json


Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/vpc>`__ to use
as reference for your use-case.
