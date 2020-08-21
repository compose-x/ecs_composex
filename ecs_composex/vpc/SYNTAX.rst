.. _vpc_syntax_reference:

x-vpc
=====

The VPC module is here to allow you to define settings for the VPC from docker-compose file directly instead of the
CLI, using the same arguments. Equally, for ease of use, you can also define lookup settings to use an existing VPC.

Creating a new VPC
-------------------

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

Use and existing VPC and subnets
---------------------------------

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

.. hint::

    The difference with Lookup is that, it won't try to find the VPC and Subnets, allow to "hardcode" static
    values.

Looking up for an existing VPC
-------------------------------

.. code-block:: yaml

    x-vpc:
      Lookup:
        VpcId:
          Tags:
            - key: value
        StorageSubnets:
            - subnet-abcd
        PublicSubnets:
          Tags:
            - vpc::usage: public
        AppSubnets: subnet-abcd,subnet-1234

Supported filters
^^^^^^^^^^^^^^^^^

VpcId
"""""

.. code-block:: yaml
    :caption: Lookup VPC ID
    :name: Lookup VPC ID

    x-vpc:
      Lookup:
        VpcId: vpc-123456

.. code-block:: yaml
    :caption: Lookup VPC ARN
    :name: Lookup VPC ARN

    x-vpc:
      Lookup:
        VpcId: arn:aws:ec2:eu-west-1:012345678912:vpc/vpc-123456

.. code-block:: yaml
    :caption: Lookup via Tags
    :name: Lookup via Tags

    x-vpc:
      Lookup:
        VpcId:
          Tags:
            - Name: vpc-shared


StorageSubnets, AppSubnets, PublicSubnets
"""""""""""""""""""""""""""""""""""""""""

If defined as a string, it will expected a *CommaDelimitedList* of valid SubnetIds.
If defined as a list, it will be expecting a list of strings of valid subnet IDs.
If defined as a object, it will expect tags list, in the same syntax as for VPC.

.. code-block:: yaml
    :caption: VPC ID
    :name: Lookup VPC ID

    x-vpc:
      Lookup:
        AppSubnets: subnet-abcd,subnet-123465,subnet-xyz

.. code-block:: yaml
    :caption: VPC ARN
    :name: Lookup VPC ARN

    x-vpc:
      Lookup:
        StorageSubnets:
          - subnet-abcd
          - subnet-12345
          - subnet-xyz

.. code-block:: yaml
    :caption: EC2 Tags
    :name: Lookup via Tags

    x-vpc:
      Lookup:
        PublicSubnets:
          Tags:
            - Name: vpc-shared


.. note::

    The AppSubnets are the subnets in which will the containers be deployed. Which means, that it requires access to
    services such as ECR, Secrets Manager etc.
    You can use any subnet in your existing VPC so long as network connectivity is achieved.


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

    If you are doing a lookup, you **must** configure the VpcId so that all subnets will be queried against that VPC
    for higher accuracy.

.. warning::

    If you specify both **Create** and **Lookup** in x-vpc, then the default behaviour is applied.
