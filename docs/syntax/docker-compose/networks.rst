.. _compose_networks_syntax_reference:

=========================
networks
=========================

In docker-compose one can define diffent subnets which would use different properties, as documented
`here <https://docs.docker.com/compose/compose-file/#network-configuration-reference>`__

This allows you to logically bind services on different networks etc, very useful in many scenarios.

In ECS ComposeX, we have added support to allow you to define these networks and logically associate them with AWS VPC Subnets.

Refer to :ref:`vpc_syntax_reference` for a full review of ECS ComposeX syntax definition for subnets mappings.


You can now define extra subnet groups based on different tags and map them to your services for override when using
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

.. code-block:: yaml
    :caption: define compose networks and associate to a Subnet category

    networks:
      custom01:
        x-vpc: Custom01

.. code-block:: yaml
    :caption: Map a compose defined network to a service

    services:
      serviceA:
        networks:
          - custom01

      serviceB:
        networks:
          custom01: {}

.. note::

    As per docker-compose config, the rendered networks in a service is a map / object. But it also can be a list.
