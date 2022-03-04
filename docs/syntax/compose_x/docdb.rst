
.. meta::
    :description: ECS Compose-X AWS DocumentDB syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS DocumentDB, MongoDB

.. _docdb_syntax_reference:

=========
x-docdb
=========

Allows you to create / lookup DocumentDB clusters you want to connect your ECS Services to.

.. tip::

    For production workloads, to avoid any CFN deadlock situations, it is recommended that
    you generate the CFN templates for docdb, and deploy the stacks separately.
    Using Lookup you can use existing DocDB clusters with your new services.

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/docdb>`__ to use
    as reference for your use-case.

.. seealso::

    For more structural details, see `JSON Schema`_

Properties
===========

DocDB Cluster is rather very simple in its configuration. There aren't 200+ combinations of EngineName and Engine Version
as for RDS, make life very easy.

However you can copy-paste all the properties you would find in the `DocDB Cluster properties`_, some properties will be
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

MacroParameters
================

These parameters will allow you to define extra parameters to define your cluster successfully.

.. code-block:: yaml

    Instances: []
    DBClusterParameterGroup: {} # AWS DocDB::DBClusterParameterGroup properties

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

DBClusterParameterGroup
------------------------

Allows you to create on-the-fly parameter groups to tune your DocDB cluster. Refer to `DocDB DBClusterParameterGroup`_
for more details.

.. code-block:: yaml
    :caption: parameter groups example

    Description: "description"
    Family: "docdb3.6"
    Name: "sampleParameterGroup"
    Parameters:
      audit_logs: "disabled"
      tls: "enabled"
      ttl_monitor: "enabled"

Services
========

Refer to :ref:`services_ref` for in-depth details.

Access
--------

For this resource, you can leave **Access** empty, the necessary Security Groups and IAM access to the DB Secret
will be done for you.

Available options
^^^^^^^^^^^^^^^^^^^

.. code-block::

    Access:
      DBCluster: RO # Grants Read/Describe access only to the DB Cluster.

ReturnValues
-------------

The available return Values are as per the `CFN return values for AWS DocDb Cluster`_
To access the *Ref* value, use **DBCluster**.

Settings
========

See :ref:`settings_syntax_reference`. Subnets supported for this resource.

Lookup
========

Lookup for this resource will accept 2 key elements

* cluster # required, allows to define how to lookup the cluster
* secret # optional, allows do point to the secret in AWS Secrets Manager that contains connection details to the Cluster.


Credentials
===========

The credentials structure remains the same as for RDS SQL versions

.. code-block:: json
    :caption: DocumentDB secret structure after attachment

    {
      "dbClusterIdentifier": "<str>",
      "password": "<str>",
      "engine": "<str>",
      "port": "<int>",
      "host": "<str>",
      "username": "<str>"
    }


Examples
========

.. literalinclude:: ../../../use-cases/docdb/create_only.yml
    :language: yaml
    :caption: Sample to crate two DBs with different instances configuration

.. literalinclude:: ../../../use-cases/docdb/create_lookup.yml
    :language: yaml
    :caption: Create a DocDB and import an existing one.


JSON Schema
============

Model
----------

.. jsonschema:: ../../../ecs_composex/specs/x-docdb.spec.json


Definition
-------------

.. literalinclude:: ../../../ecs_composex/specs/x-docdb.spec.json


.. _DocDB Cluster properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbcluster.html
.. _DocDB Instance: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbinstance.html
.. _DocDB DBClusterParameterGroup: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbclusterparametergroup.html
.. _CFN return values for AWS DocDb Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-docdb-dbcluster.html#aws-resource-docdb-dbcluster-return-values
