.. _docdb_syntax_reference:

=========
x-docdb
=========

Syntax
=======

.. code-block:: yaml

    x-docdb:
      docdb-01:
        Properties: {}
        Settings: {}
        Services: []
        Lookup: {}
        MacroParameters: {}

Properties
===========

DocDB Cluster is rather very simple in its configuration. There aren't 200+ combinations of EngineName and Engine Version
as for RDS, make life very easy.

Howerver you can copy-paste all the properties you would find in the `DocDB Cluster properties`_, some properties will be
ignored in order to keep the automation going:

* MasterUsername and MasterUserPassword
    These two will be auto generated and stored in secrets manager. The services linked to it will be granted **GetSecretValue** to it.

* VpcSecurityGroupIds
    The security group will be generated for the DB specifically and allow services listed only.

* AvailabilityZones
    Under trial, but not sure given that we give a Subnet Group why one would also define the AZs and it might conflict.

* DBClusterIdentifier
    As usual, named resources make for a nightmare to rename etc. Instead, there will be a **Name** tag associated with your Cluster.

* DBSubnetGroupName
    Equally gets created only. For now.

* SnapshotIdentifier
    Untested - 2020-11-13 - will support it later.


Services
========

The syntax for listing the services remains the same as the other x- resources.

.. code-block:: yaml

    Services:
      - name: <service/family name>
        access: <str>

Access types
------------

.. warning::

    The access key value do not have an effect at this stage.

Settings
========

The only setting for DocumentDB is **EnvNames** as for every other resources.

.. hint::

    Given that the DB Secret attachment populates host, port etc., we expose as env vars the **Secret** associated to the DB,
    not the DB itself.

MacroParameters
================

These parameters will allow you to define extra parameters to define your cluster successfully.
In the future you should be able to define your `DocDB Cluster Parameters`_ there.

Instances
---------

List of DocDB instances. The aspiration is to follow the same syntax as the `DocDB Instance`_.

.. note::

    Not all Properties are respected, instead, they follow logically the attachment to the DocDB Cluster.


.. code-block:: yaml

    Instances:
      - DBInstanceClass: <db instance type>
        PreferredMaintenanceWindow: <window definition>
        AutoMinorVersionUpgrade: bool


.. hint::

    If you do not define an instance, ECS ComposeX automatically creates a new one with a single node of type **db.t3.medium**


Lookup
========

Lookup for Document DB is available!

.. warning::

    For some reason the group resource tag API returns two different clusters even though they are the same one.
    Make sure to specify the *Name* along with Tags until we figure an alternative solution.
    Sorry for the inconvenience.


Examples
========

.. literalinclude:: ../../../use-cases/docdb/create_only.yml
    :language: yaml
    :caption: Sample to crate two DBs with different instances configuration

.. literalinclude:: ../../../use-cases/docdb/create_lookup.yml
    :language: yaml
    :caption: Create a DocDB and import an existing one.


.. _DocDB Cluster properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbcluster.html
.. _DocDB Instance: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbinstance.html
.. _DocDB Cluster Parameters: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbclusterparametergroup.html
