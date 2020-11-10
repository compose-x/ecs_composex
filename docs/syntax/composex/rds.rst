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

RDS cluster or instances need a lot of parameters. At this stage, you would not copy the settings as defined on AWS CFN
documentation, simply because a lot of it is done automatically for you. The plan is to use the settings in the future
to drive changes and some more properties (ie. snapshots) will be added to allow for far more use-cases.

.. hint::

    Technically, the use of snapshots is already implemented, but not fully tested. Stay tuned for next update!

Mandatory properties
---------------------

The properties follow the `Aurora Cluster properties <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html>`_
as I have more use-cases for using Aurora than using traditional RDS. Cluster and DB Instance share a lot of common properties
so therefore the difference will be very minor in the syntax.

* `Engine`_
* `EngineVersion`_


Special Properties
-------------------

No special properties available for RDS yet.

Services
========

At this point in time, there is no plan to deploy as part of ECS ComposeX a lambda function that would connect to the DB
and create a DB/schema specifically for the microservice, as would `this lambda function <https://github.com/lambda-my-aws/rds-auth-helper>`_ do.

The syntax for listing the services remains the same as the other x- resources but the access type won't be respected.

Access types
------------

.. warning::

    The access key value won't be respected at this stage.

Settings
========

Some use-cases require special adjustments. This is what this section is for.

copy_default_parameters
-----------------------

Type: boolean
Default: True  when using aurora

Creates a DBClusterParameterGroup automatically so you can customize later on your CFN template for the DB Settings.
This avoids the bug where only default.aurora-mysql5.6 settings are found if the property is not set.

.. tip::

    The function performing the import of settings in ecs_composex.rds.rds_parameter_groups_helper.py

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

    The DB Family group will be found automatically and the setting `copy_default_parameters`_ will allow creation of a
    new RDS Parameter group for the Cluster / DB Instance.


.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
