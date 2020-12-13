.. _rds_syntax_reference:

=====
x-rds
=====

Syntax
=======

.. code-block:: yaml

    x-rds:
      psql-dbA:
        Properties: {}
        Settings: {}
        Services: []
        Lookup: {}

Properties
===========

RDS clusters or instances need a lot of properties. In order to keep compatibility you can still provide all the properties
that the RDS Cluster or RDS Instance would need with the same definition as in AWS CloudFormation.

However, some settings will be replaced automatically (at least for the foreseeable future), such as the master username
and password. The reason for it is to allow to keep integration to your ECS Services as seamless as possible.

Using properties
---------------------

When using Properties, you can use either the `RDS Aurora Cluster`_ properties or `RDS Instances`_ properties.
ECS ComposeX will attempt to automatically identify whether this is a DB Cluster or DB Instance properties set.
If successful, it will ingest all your properties, and explained earlier, interpolate a few with new ones created for you.


* `MasterUsername <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-database-instance.html#cfn-rds-dbinstance-masterusername>`__
* `MasterUserPassword <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-database-instance.html#cfn-rds-dbinstance-masteruserpassword>`__
* `Security Groups <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-database-instance.html#cfn-rds-dbinstance-vpcsecuritygroups>`__


MacroParameters
=================

MacroParameters for RDS allow you to set only very little settings / properties and let ECS ComposeX do the rest for you.

.. code-block:: yaml
    :caption: MacroParameters syntax

    Engine: str
    EngineVersion: str
    UseServerless: bool
    UseMultiAz: bool
    ParametersGroup: {} # Properties for parameters group as per AWS CFN definition
    Instances: [] # Only valid when creating a DBCluster, allows to define multiple DB Instances

.. code-block:: yaml
    :caption: MacroParameters definitions example

    Engine: aurora-postgresql # Same as AWS CFN Engine property
    EngineVersion: 11.7 # Same as AWS CFN EngineVersion property
    UseServerless: False
    UseMultiAz: True
    ParametersGroups:
      Description: Some description
      Family: aurora-postgresql-11.7
      Parameters: {}
    Instances: []


Services
========

At this point in time, there is no plan to deploy as part of ECS ComposeX a lambda function that would connect to the DB
and create a DB/schema specifically for the microservice, as would `this lambda function <https://github.com/lambda-my-aws/rds-auth-helper>`_ do.

The syntax for listing the services remains the same as the other x- resources but the access type won't be respected.

Access types
------------

.. warning::

    The access key value won't be respected at this stage. This is required to keep compatibility with other modules.

Settings
========

.. code-block:: yaml
    :caption: Supported Settings

    EnvNames: [<str>] # List of Environment Variable names to use for exposure to container

Lookup
======

The lookup allows you to find your cluster or db instance and also the Secret associated with them to allow ECS Services
to get access to these.

It will also find the DB security group and add an ingress rule.

.. code-block:: yaml

    x-rds:
      dba:
        Lookup:
          cluster:
            Name: cluster-identifier
            Tags:
              - sometag: value
          instance:
            Name: DB Instance Id
            Tags:
              - sometag: value
          secret:
            Tags:
              - sometag: value
            Name: secret/in/secretsmanager

When using AWS RDS Aurora, you should be specifying the cluster, otherwise the instance for "traditional" RDS instances.

Defaults
===========

Credentials
-----------

Aurora and traditional RDS Databases support both Username/Password generic authentication. Due to the wide adoption of
that authentication mechanism, all RDS Dbs will come with a username/password, auto generated and stored in AWS Secrets Manager.


.. hint::

    We do plan to allow a tick button to enable Aurora authentication with IAM, however have not received a Feature Request
    for it.

AWS Secrets Manager integrates very nicely to AWS RDS. This has no intention to implement the rotation system at this
point in time, however, it will generate the password for the database and expose it securely to the microservices which
can via environment variables fetch

* DB Endpoint
* DB username
* DB Password
* DB Port


Examples
========

.. code-block:: yaml
    :caption: New DB Creation

    x-rds:
      dbname:
        Properties:
          Engine: aurora-mysql
          EngineVersion: 5.7.12
        Services:
          - name: app01
            access: RW


.. code-block:: yaml
    :caption: Existing Cluster DB Lookup

    x-rds:
      existing-cluster-dbA:
        Lookup:
          cluster:
            Tags:
              - key: value
          secret:
            Tags:
              - key: value


.. hint::

    The DB Family group will be found automatically and the setting will allow creation of a
    new RDS Parameter group for the Cluster / DB Instance.


.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
.. _RDS Aurora Cluster: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html
.. _RDS Instances: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-rds-database-instance.html
