.. meta::
    :description: ECS Compose-X AWS RDS syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS RDS, mysql, postresql, rds

.. _rds_syntax_reference:

=====
x-rds
=====

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/rds>`__ to use
    as reference for your use-case.

Syntax
=======

.. code-block:: yaml

    x-rds:
      psql-dbA:
        Properties: {}
        MacroParameters: {}
        Settings: {}
        Services: []
        Lookup: {}

Properties
===========

RDS clusters or instances need a lot of properties. In order to keep compatibility you can still provide all the properties
that the RDS Cluster or RDS Instance would need with the same definition as in AWS CloudFormation.

However, some settings will be replaced automatically (at least for the foreseeable future), such as the master username
and password. The reason for it is to allow to keep integration to your ECS Services as seamless as possible.

.. note::

    When using Properties, you can use either the `RDS Aurora Cluster`_ properties or `RDS Instances`_ properties.
    ECS ComposeX will attempt to automatically identify whether this is a DB Cluster or DB Instance properties set.
    If successful, it will ingest all your properties, and explained earlier, interpolate a few with new ones created for you.

Properties overridden
----------------------

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
    ParametersGroup: {}         # Properties for parameters group as per AWS CFN definition
    Instances: []               # Only valid when creating a DBCluster, allows to define multiple DB Instances
    RdsFeatures: {}             # Custom settings to define AWS RDS AssociatedRoles
    PermissionsBoundary: str    # Allow you to define an IAM boundary policy that will be used for the RDS IAM role(s)

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
    RdsFeatures:
      - Name: s3Import
        Resources:
          - x-s3::bucket-01
          - arn:aws:s3:::bucket/path/allowed/*
          - bucket-name


PermissionsBoundary
-------------------

Allows to define whether an IAM Policy boundary is required for the IAM roles that will be created around the RDS Cluster/Instance.

.. hint::

    This value can be either a policy name or policy ARN. When a policy Name, the ARN is built based on your Account ID.

RdsFeatures
------------

.. code-block:: yaml
    :caption: Syntax definition

    RdsFeatures:
      - Name: <DB Engine feature name>
      - Resources: [<str>]


The RDS Features is a wrapper to automatically define which RDS Features, supported by the Engine family, you might
want to enable. For these features, which require an IAM role, it will create a new IAM role specifically linked to
RDS and grant permissions based on the what the feature requires.

If you had set **AssociatedRoles** already in the permissions, then each *FeatureName* you have already defined that you
might re-define in **RdsFeatures** will be skipped. If you wish to use **RdsFeatures** then remove that feature from the
**AssociateRoles** definition.


.. attention::

    This was primarily developed to allow feature request #375 so at the moment it only supports s3Import and s3Export.


.. code-block:: yaml
    :caption: Example with different bucket names syntax

    x-rds:
      dbB:
        Properties: {}
        MacroParameters:
          PermissionsBoundary: policy-name
          RdsFeatures:
            - Name: s3Import
              Resources:
                - x-s3::bucket-01
                - arn:aws:s3:::sacrificial-lamb/folder/*
                - bucket-name
            - Name: s3Export
              Resources:
                - x-s3::bucket-01
                - arn:aws:s3:::sacrificial-lamb/folder/*
                - bucket-name

.. hint::

    You can reference a S3 bucket defined in **x-s3**. This supports S3 buckets created and referenced via Lookup



Services
========

List of the services that we want to provide access to the database.

name
------

The name of the service we want to grant the access to.

access
------------

.. warning::

    The access key value won't be respected at this stage. This is required to keep compatibility with other modules.
    Any string value will work at this time.

SecretsMapping
---------------

This is an optional feature that allows you to map the secret key stored into Secrets Manager (see `Credentials`_) to a different
environment variable.

.. code-block:: yaml
    :caption: Sample for bitnami wordpress application

    x-rds:
      wordpress-db:
        Properties:
          Engine: "aurora-mysql"
          EngineVersion: "5.7"
          BackupRetentionPeriod: 1
          DatabaseName: wordpress
          StorageEncrypted: True
          Tags:
            - Key: Name
              Value: "dummy-db"
        Services:
          - name: wordpress
            access: RW
            SecretsMappings:
              Mappings:
                host: MARIADB_HOST
                port: MARIADB_PORT_NUMBER
                username: WORDPRESS_DATABASE_USER
                password: WORDPRESS_DATABASE_PASSWORD
                dbname: WORDPRESS_DATABASE_NAME

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


AWS Secrets Manager integrates very nicely to AWS RDS. This has no intention to implement the rotation system at this
point in time, however, it will generate the password for the database and expose it securely to the microservices which
can via environment variables fetch

After attachment between the RDS and the secret, the secret will not only contain the username and password, but additional
information that is required by your application to connect to the database.

.. code-block:: json

    {
      "password": "string<>"
      "dbname": "string<>",
      "engine": "string<>",
      "port": int<port>,
      "host": "string<>"
      "username": "string<>"
    }

.. hint::

    We do plan to allow a tick button to enable Aurora authentication with IAM, however have not received a Feature Request
    for it.


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
