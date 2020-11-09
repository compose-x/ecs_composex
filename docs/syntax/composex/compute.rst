.. _compute_syntax_reference:

========================
spot_config
========================

This module is not strictly a module which the same settings as the other AWS resources. This is a module which allows
users to create the EC2 compute resources necessary to run the ECS Containers on top of EC2 workloads.

.. note::

    At this point in time, there is no support for creating Capacity providers in CloudFormation, therefore we cannot
    implement that functionality.

.. note::

    By default, everything is built to use EC2 spot fleet, simply to save money on deployment for testing.
    Future will allow to run pure OnDemand or hybrid mode.

.. _compute syntax reference:

Define settings in the configs section
---------------------------------------

At the moment, the settings you can change for the compute definition of your EC2 resources are defined in

configs -> globals -> spot_config

Example:

.. code-block:: yaml

    x-configs:
      spot_config:
        bid_price: 0.42
        use_spot: true
        spot_instance_types:
        m5a.xlarge:
          weight: 4
        m5a.2xlarge:
          weight: 8
        m5a.4xlarge:
          weight: 16

With the given AZs of your region, it will create automatically all the overrides to use the spot instances.

.. note::

    This spotfleet comes with a set of predefined Scaling policies, in order to further reduce cost or allow for
    scaling out based on EC2 metrics.


.. warning::

    We cannot recommend any more to use AWS Fargate and configure your capacity providers instead of EC2 instances.
    Use with caution
