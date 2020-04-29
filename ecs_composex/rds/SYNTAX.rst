ecs_composex.rds
================

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

Services list
--------------

At this point in time, there is no plan to deploy as part of ECS ComposeX a lambda function that would connect to the DB
and create a DB/schema specifically for the microservice, as would `this lambda function <https://github.com/lambda-my-aws/rds-auth-helper>`_ do.

The syntax for listing the services remains the same as the other x- resources but the access type won't be respected.

Mandatory Properties
--------------------

The properties follow the `Aurora Cluster properties <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html>`_
as I have more use-cases for using Aurora than using traditional RDS. Cluster and DB Instance share a lot of common properties
so therefore the difference will be very minor in the syntax.

* `Engine`_
* `EngineVersion`_


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

.. warning::

    mysql 5.6 is no longer available for Aurora.


.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
