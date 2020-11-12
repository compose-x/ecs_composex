
.. _dns_reference_syntax:

======
x-dns
======

Allows you to indicate what the DNS settings shall be for the deployment of your containers.

Syntax
======

.. code-block:: yaml

    PrivateNamespace:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap ns- namespace ID

.. warning::

    This domain will be associated with the VPC Route53 "database". If another Namespace using the same domain
    name already is associated with the VPC, this will fail.


.. code-block::

    PublicNamespace:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap ns- namespace ID


.. warning::

    When using CloudMap for public namespace, you CAN NOT use AWS-ACM DNS validation method!

.. code-block::

    PublicZone:
      Name: str # TLD to use for the deployment.
      Lookup: str # Domain name to find in CloudMap
      Use: str # Expects the CloudMap Z[A-Z0-9]+- Hosted Zone Id


Example
=======

.. code-block:: yaml
    :caption: Private definition only

    x-dns:
      PrivateNamespace:
        Name: mycluster.lan

.. code-block:: yaml
    :caption: Public Zone and private zone

    x-dns:
      PrivateNamespace:
        Use: ns-abcd012344
      PublicZone:
        Use: Z0123456ABCD
