
.. meta::
    :description: ECS Compose-X advanced network syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, networking, subnets, vpc, cloudmap

.. _x_configs_network_syntax:

==================
services.x-network
==================

.. code-block:: yaml

    services:
      serviceA:
        x-network:
          x-ecs_connect: {}
          AssignPublicIp: bool
          Ingress: {}
          x-cloudmap: {}

.. _public_eip_for_service_option:

AssignPublicIp
===============

This flag allows to assign an Elastic IP to the container when using ``awsvpc`` networking mode.

.. hint::

    Make sure to set your service to be in a subnet that use an ``Internet Gateway``, such as ``PublicSubnets``, otherwise
    routing won't work.

.. tip::

    See :ref:`how_to_service_public_eip` to have a full example of how to implement this feature.

.. _services_ingress_syntax_reference:

.. tip::

    To select which subnets to place the services, see :ref:`compose_networks_syntax_reference`


x-ecs_connect (1.1.0)
======================

This configuration section allows you to define ECS Service Connect configuration.
It's made up of two options, `Properties` and `MacroParameters`

`Properties` must match exactly the `ECS Service Connect properties`_ and must be all valid to work.

.. attention::

    No changes to input or validation will be made when set. Be sure to have everything valid.

`MacroParameters` however, is an attempt at creating a shorthand syntax to this.

service connect - client only
------------------------------

You might have applications that you want to act only as clients to other services. This will only tell ECS to make sure
to provision the Service Connect sidecar which will be there to handle the proxy-ing to server services.

To enable the client config, you simply need to enable the feature as show below

.. code-block::

    x-cloudmap:
      PrivateNamespace:
        Name: compose-x.internal

    services:
      yelb-ui:
        x-network:
          AssignPublicIp: true
          x-ecs_connect:
            MacroParameters:
              x-cloudmap: PrivateNamespace
          Ingress:
            ExtSources:
              - IPv4: 0.0.0.0/0
                Name: ANY

service connect - server
----------------------------

For services that you want to act as client & server, you need to declare which ports you want to declare to Service Connect.
That's mandatory.

For example, we have the following two services: appserver will act as both a client and a server. It will serve requests
for our yelb-ui service (the client above), and a client to the redis-server

.. code-block::

    x-cloudmap:
      PrivateNamespace:
        Name: compose-x.internal

    services:
      yelb-appserver:
        image: mreferre/yelb-appserver:0.7
        depends_on:
          - redis-server
        ports:
          - 4567:4567
        environment:
          redishost: redis-server
        x-network:
          Ingress:
            Services:
              - Name: yelb-ui
          x-ecs_connect:
            MacroParameters:
              service_ports:
                tcp_4567:
                  DnsName: yelb-appserver
                  CloudMapServiceName: yelb-appserver
              x-cloudmap: PrivateNamespace


      redis-server:
        image: redis:4.0.2
        ports:
          - 6379:6379
        x-network:
          x-ecs_connect:
            MacroParameters:
              service_ports:
                tcp_6379:
                  DnsName: redis-server
                  CloudMapServiceName: redis-server
              x-cloudmap: PrivateNamespace
          Ingress:
            Services:
              - Name: yelb-appserver

.. hint::

    See `the full connect example`_ uses to perform functional testing of the feature.

Ingress
======================

This allows you to define specific ingress control from external sources to your environment. For example, if you have
to whitelist IP addresses that are to be allowed communication to the services, you can list these, and indicate their
name which will be shown in the EC2 security group description of the ingress rule.

Ingress Syntax reference
-----------------------------

.. code-block:: yaml

    Ingress:
      ExtSources: []
      AwsSources: []
      Myself: True/False

.. code-block:: yaml
    :caption: Ingress Example

    services:
      app01:
        x-network:
          Ingress:
            ExtSources:
              - IPv4: 0.0.0.0/0
                Name: all
              - IPv4: 1.1.1.1/32
                Source_name: CloudFlareDNS
            AwsSources:
              - Type: SecurityGroup
                Id: sg-abcd
              - Type: PrefixList
                Id: pl-abcd
            Myself: True/False

.. tip::

    You can define the SG from another AWS account by setting ``AccountOwner`` in the Security group definition.

.. tip::

    You can define which ports to open per source using the ``Ports`` list.

    .. hint::

        If you enter a port number that is not in the ``Ports`` list, it will be ignored.

.. hint::

    The protocol is automatically detected based on the port definition.
    By default, it is TCP

.. hint::

    To see details about the Ingress for Load Balancers, refer to :ref:`load_balancers_ingress_syntax_ref`


.. hint::

    When using an ALB, you do not need to define that ALB security group etc., all inbound rules will be defined automatically
    to allow the ALB to communicate with your service!

x-cloudmap
-----------

Refer to :ref:`cloudmap_reference_syntax` for more details on how to use it.

Map VPC subnets to docker-compose networks
===========================================

.. code-block:: yaml
    :caption: AWS VPC to network mapping

    networks:
      internal:
        x-vpc: InteralCustomSubnets

    x-vpc:
      VpcId:
        Tags: []
      AppSubnets:
        Tags: []
      PublicSubnets:
        Tags: []
      StorageSubnets:
        Tags: []
      InteralCustomSubnets:
        Tags: []

    services:
      serviceA:
        networks: [internal]


JSON Schema
============

Model
------

.. jsonschema:: ../../../../ecs_composex/specs/services.x-network.spec.json

Definition
-----------

.. literalinclude:: ../../../../ecs_composex/specs/services.x-network.spec.json

.. _ECS Service Connect properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-ecs-service-serviceconnectconfiguration.html
.. _the full connect example: https://github.com/compose-x/ecs_composex/tree/main/use-cases/yelb.yaml
