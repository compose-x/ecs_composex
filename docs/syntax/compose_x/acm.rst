
.. meta::
    :description: ECS Compose-X ACM syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS ACM, SSL Certificates

.. _acm_syntax_reference:

=================
x-acm
=================

This module allows you to define new ACM Certificates (with DNS Validation) or import existing ones that you wish
to use with supported AWS services and resources.

Syntax Reference
=================

    x-acm:
      certificate:
        Properties: {}
        MacroParameters: {}
        Lookup: {}

Properties
==========

Full support of AWS ACM native properties. Refer to `AWS ACM Properties`_

.. hint::

    If you defined multiple **SubjectAlternativeNames** names, they will be auto-added to the validation list and use
    the same ZoneId, so you do not need to list them all in `DomainValidationOptions`_


MacroParameters
================

This automatically creates the full ACM Certificate definition, and uses DNS validation with AWS CloudFormation.
All you have to do is list the domain names that you wish to have in the certificate and the x-route53 or HostedZoneID
that you will allow for DNS validation to succeed.

.. code-block:: yaml
    :caption: example using macro parameters and x-route53

    x-acm:
      PublicELBCert:
        MacroParameters:
            DomainNames:
              - domain.tld
              - sub.domain.tld
            HostedZoneId: x-route53::public-domain # Alternatively, you can set the hosted zone ID directly.

    x-route53:
      public-domain:
        ZoneName: domain.tld
        Lookup: true

DomainNames
-----------

List of the domain names you want to create the ACM Certificate for.

.. hint::

    The first domain name will be used for the CN, and the following ones will be used for SubjectAlternative names

HostedZoneId
------------

The pointer to the x-route53 domain that will allow for DNS Validation. If however you prefer to enter the HostedZoneID
directly, you can (or use environment variable).

.. attention::

    That HostedZone ID will be used for *all* of the Domain Validation.


Services
========

No need to indicate services to assign the ACM certificate to. Refer to :ref:`elbv2_syntax_reference` for mapping
to ALB/NLB.


Example
=======

.. code-block:: yaml
    :caption: Using CFN Properties

    x-acm:
      public-acm-01:
        Properties:
          DomainName: test.lambda-my-aws.io
          DomainValidationOptions:
            - HostedZoneId: ZABCDEFGHIS0123
              DomainName: test.lambda-my-aws.io
          SubjectAlternativeNames:
            - anothertest.lambda-my-aws.io
            - yet.another.test.lambda-my-aws.io
          ValidationMethod: DNS

.. hint::

    If you need to specify ``x-dns`` in the template and provide the **HostedZoneId** which will be used there.
    DNS Reference: :ref:`dns_reference_syntax`

JSON Schema
=============

Model
---------------

.. jsonschema:: ../../../ecs_composex/acm/x-acm.spec.json


Definition
-----------

.. literalinclude:: ../../../ecs_composex/acm/x-acm.spec.json


Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/acm>`__
to use as reference for your use-case.


.. _AWS ACM Properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-certificatemanager-certificate.html
.. _DomainValidationOptions: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-certificatemanager-certificate.html#cfn-certificatemanager-certificate-domainvalidationoptions
