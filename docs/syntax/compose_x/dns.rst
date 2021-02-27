.. meta::
    :description: ECS Compose-X DNS configuration
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. _dns_reference_syntax:

======
x-dns
======

Allows you to indicate what the DNS settings shall be for the deployment of your containers.

Syntax
======

.. code-block:: yaml
    :caption: Private Namespace definition (Uses AWS CloudMap)

    PrivateNamespace:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap ns- namespace ID

.. warning::

    This domain will be associated with the VPC Route53 "database". If another Namespace using the same domain
    name already is associated with the VPC, this will fail.

.. code-block::
    :caption: Public DNS Zone using Route53.

    PublicZone:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap Z[A-Z0-9]+- Hosted Zone Id

.. attention::

    For ACM DNS Validation and other validations to work, the zone must be able to be resolved.

Examples
=========

.. code-block:: yaml
    :caption: Private definition only

    x-dns:
      PrivateNamespace:
        Name: mycluster.lan

.. code-block:: yaml
    :caption: Public Zone and private zone

    x-dns:
      PrivateNamespace:
        Name: mycluster.lan
        Use: ns-abcd012344
      PublicZone:
        Name: public-domain.net
        Use: Z0123456ABCD
