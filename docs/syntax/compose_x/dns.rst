.. meta::
    :description: ECS Compose-X DNS configuration
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS Route53, AWS CloudMap, dns

.. _dns_reference_syntax:

======
x-dns
======

.. contents::
    :depth: 2

`JSON Schema Definition <https://github.com/compose-x/ecs_composex_specs/blob/main/ecs_composex_specs/x-dns.spec.json>`_

PrivateNamespace (AWS CloudMap)
---------------------------------

.. code-block:: yaml
    :caption: Private Namespace definition (Uses AWS CloudMap)

    PrivateNamespace:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap ns- namespace ID

.. warning::

    When creating a new one, this domain will be associated with the VPC Route53 "database".
    If another Namespace using the same domain name already is associated with the VPC, this will fail.

Public Zone (Route53)
----------------------

.. code-block::
    :caption: Public DNS Zone using Route53.

    PublicZone:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap Z[A-Z0-9]+- Hosted Zone Id

.. attention::

    For ACM DNS Validation and other validations to work, the zone must be able to be resolved otherwise automated
    validation will not work.


DNS records
--------------

This section of x-dns allows you to define DNS Records pointing to resources defined in the compose-x files.

The record properties follow the same properties as `AWS Route53 RecordSet`_

When the target is an ELBv2 it automatically creates an `alias`_ record.

Examples
---------

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

.. code-block:: yaml
    :caption: Private and public zone with a DNS record pointing to an ELBv2

    x-dns:
      PrivateNamespace:
        Name: dev.internal
        Lookup:
          RoleArn: ${NONPROD_RO_ROLE_ARN}

      PublicZone:
        Name: dev.my-domain.net
        Lookup:
          RoleArn: ${NONPROD_RO_ROLE_ARN}

      Records:
        - Properties:
            Name: controlcenter.dev.my-domain.net
            Type: A
          Target: x-elbv2::controlcenter


.. _AWS Route53 RecordSet: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-route53-recordset.html
.. _alias: https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-choosing-alias-non-alias.html
