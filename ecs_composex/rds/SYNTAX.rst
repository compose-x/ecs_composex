ecs_composex.rds
================

.. contents::

.. code-block:: yaml

    x-rds:
      dbname:
        Properties:
          Engine: aurora-mysql
          EngineVersion: 5.7.12
        Services:
          - name: app01
            access: RW


.. hint::

    The DB Family group will be found automatically and the setting `copy_default_parameters`_ will allow creation of a
    new RDS Parameter group for the Cluster / DB Instance.

Services
--------

At this point in time, there is no plan to deploy as part of ECS ComposeX a lambda function that would connect to the DB
and create a DB/schema specifically for the microservice, as would `this lambda function <https://github.com/lambda-my-aws/rds-auth-helper>`_ do.

The syntax for listing the services remains the same as the other x- resources but the access type won't be respected.

.. warning::

    The access key value won't be respected at this stage.

Settings
--------

Some use-cases require special adjustments. This is what this section is for.

copy_default_parameters
^^^^^^^^^^^^^^^^^^^^^^^

Type: boolean
Default: True  when using aurora

Creates a DBClusterParameterGroup automatically so you can customize later on your CFN template for the DB Settings.
This avoids the bug where only default.aurora-mysql5.6 settings are found if the property is not set.

.. tip::

    The function performing the import of settings in ecs_composex.rds.rds_parameter_groups_helper.py

Properties
--------------------

RDS cluster or instances need a lot of parameters. At this stage, you would not copy the settings as defined on AWS CFN
documentation, simply because a lot of it is done automatically for you. The plan is to use the settings in the future
to drive changes and some more properties (ie. snapshots) will be added to allow for far more use-cases.

.. hint::

    Technically, the use of snapshots is already implemented, but not fully tested. Stay tuned for next update!

Mandatory properties
^^^^^^^^^^^^^^^^^^^^

The properties follow the `Aurora Cluster properties <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html>`_
as I have more use-cases for using Aurora than using traditional RDS. Cluster and DB Instance share a lot of common properties
so therefore the difference will be very minor in the syntax.

* `Engine`_
* `EngineVersion`_



.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
