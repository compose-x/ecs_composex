.. _aws_docdb_readme:

=======================
AWS DocumentDB (DocDB)
=======================

DocumentDB is yet another great implementation of a popular service (MongoDB) made as a service with the harvest power
of AWS Storage.

Similar in many many ways to RDS Aurora clusters with MySQL and PostgreSQL compatibility, this time, for MongoDB.

Properties
==========

AWS DocDB Cluster configuration is a lot simplier than its SQL cousins. With very minimum properties, you can, using ComposeX,
deploy clusters and automatically link these to your services.

.. tip::

    For production workloads, to avoid any CFN deadlock situations, I recommend you generate the CFN templates for docdb,
    and deploy the stacks separately. Using Lookup you can use existing DocDB clusters with your new services.


Credentials
===========

The credentials strucutre remains the same as for RDS SQL versions

.. code-block:: json
    :caption: DocumentDB secret structure after attachment

    {
      "dbClusterIdentifier": "<str>",
      "password": "<str>",
      "engine": "<str>",
      "port": <int>,
      "host": "<str>",
      "username": "<str>"
    }
