.. _vpc_syntax_reference:

======
x-vpc
======

The VPC module is here to allow you to define settings for the VPC from docker-compose file directly.
Equally, for ease of use, you can also define lookup settings to use an existing VPC.

Syntax
======

.. code-block:: yaml

    x-vpc:
      Create: {}
      Lookup: {}
      Use: {}

Create
======

.. code-block::

    x-vpc:
      Create:
        SingleNat: true
        VpcCidr: 172.6.7.42/24
        Endpoints:
          AwsServices:
            - service: s3
            - service: ecr.api
            - service: ecr.dkr

SingleNat
---------

Whether you want to have 1 NAT per AZ for your application subnets.
Reduces the costs for dev environments!


VpcCidr
--------

The CIDR you want to use. Default is **100.127.254.0/24**.

Endpoints
----------

List of VPC Endpoints from AWS Services you want to create.
Default will create Endpoints for ECR (DKR and API).

EnableFlowLogs
--------------

Whether you want to have a VPC Flow Log created for the VPC.
It will create a new LogGroup and IAM Role to allow logging to CloudWatch.

FlowLogsRoleBoundary
--------------------

For those of you who require IAM PermissionsBoundary for your IAM Roles, this allows to set the boundary.
If it starts with **arn:aws** it will assume this is a valid ARN, otherwise, it will use the value as
policy name.


Use
===

.. code-block:: yaml

    x-vpc:
      Use:
        VpcId: vpc-id
        AppSubnets:
          - subnet-id
          - subnet-id
        StorageSubnets:
          - subnet-id
          - subnet-id
        PublicSubnets:
          - subnet-id
          - subnet-id

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

.. tip::

    When you are looking up for the VPC and Subnets, these parameters are added to ComposeX.
    At the time of rendering the template to files, it will also create a params.json file for the stack, and put
    your VPC ID and Subnets IDs into that file.

    .. code-block:: json

        [
            {
                "ParameterKey": "VpcId",
                "ParameterValue": "vpc-01185d1aad942441c"
            },
            {
                "ParameterKey": "AppSubnets",
                "ParameterValue": "subnet-00ad888b1434a7187,subnet-04d5d90d04874f8e2,subnet-04103167a162e3f8e"
            },
            {
                "ParameterKey": "StorageSubnets",
                "ParameterValue": "subnet-0dc9044f0b566c878,subnet-0fe6f4beb6ce2403d,subnet-0aa49c83e98120a5d"
            },
            {
                "ParameterKey": "PublicSubnets",
                "ParameterValue": "subnet-005eb795e33b68464,subnet-0fb1855c9316aab3c,subnet-0f4f3d27a17b1c3da"
            },
            {
                "ParameterKey": "VpcDiscoveryMapDnsName",
                "ParameterValue": "cluster.local"
            }
        ]

.. warning::

    If you specify both **Create** and **Lookup** in x-vpc, then the default behaviour is applied, and creates a new VPC
