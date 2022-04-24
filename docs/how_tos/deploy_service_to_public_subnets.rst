
.. meta::
    :description: ECS Compose-X How To
    :keywords: AWS, docker, compose, public, networking, subnets

################################################
Deploy services with EIP on public subnets
################################################

By default, services will be deployed into the ``AppSubnets``, which are behind a NAT to access the internet,
and will need an ELBv2 or some publicly addressed appliance to forward requests to.

There will be use-cases where you might not need private subnets, or simply might want to deploy services publicly addressed.

Thanks to Max R. for bringing this use-case.

x-vpc - Configuration
======================

Where the `services and networks`_ will be the same for both using a new VPC or an existing one (and therefore its subnets),
here is how you define a new VPC you wish to create without NAT gateway(s), and another using existing subnets.

With a new VPC
---------------------

So let's assume you are at the testing phase of your development and are ready to deploy your service.
You don't yet have an infrastructure, so you let ECS Compose-X create the VPC for you.

You know the service should be publicly addressed, so you won't need a NAT Gateway or other endpoints.
Your ``x-vpc`` definition then looks as follows:

.. code-block:: yaml
    :caption: x-vpc block in the compose file

    x-vpc:
      Properties:
        VpcCidr: 192.168.0.0/24 # A simple CIDR with plenty of room for the deployment.
        DisableNat: True        # Although the Public, App and Storage subnets are created, no NAT nor route is created.
        Endpoints: {} # Set to {} to disable creating the default VPC endpoints Compose-X use. We won't be needing them.

With an existing VPC
------------------------

To use an existing VPC and its subnets, we simply define the following Lookup which will identify all subnets.

.. code-block:: yaml
    :caption: very simplified x-vpc.Lookup

    x-vpc:
      Lookup:
        VpcId:
          Tags:
            - Name: my-existing-vpc
        AppSubnets:
          Tags:
            - usage: application
        StorageSubnets:
          Tags:
            - usage: storage
        PublicSubnets:
          Tags:
            - usage: public


services and networks
========================

We are going to use a simple example, NGINX container, listening on port 80.

We have defined a docker network, ``public``, which uses the ``x-vpc: PublicSubnets`` binding. That will automatically
change the subnet IDs to use for the service, to use the ``PublicSubnets`` instead of ``AppSubnets``.

Then, we indicate in our network settings that our service must have the Property `AssignPublicIp`_ set to True.

.. hint::

    You can use a yaml boolean or the CFN values, "ENABLED" or "DISABLED". When using boolean, CFN values are automatically used.

.. code-block:: yaml

    version: "3.8"
    networks:
      public:
        x-vpc: PublicSubnets

    services:
      nginx:
        image: nginx
        ports:
          - 80:80/tcp
        networks:
          public:

        x-network:
          AssignPublicIp: true


.. _AssignPublicIp: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-awsvpcconfiguration.html#cfn-ecs-service-awsvpcconfiguration-assignpublicip
