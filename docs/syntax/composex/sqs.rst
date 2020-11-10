.. _sqs_syntax_reference:

======
x-sqs
======

Syntax
=======

.. code-block:: yaml
    :caption: SNS Syntax Reference

    x-sns:
      QueueA:
        Properties: {}
        Settings: {}
        Services: []

Properties
==========

Mandatory Properties
^^^^^^^^^^^^^^^^^^^^^

SQS does not require any properties to be set in order to create the queue. No settings are mandatory.

Special properties
^^^^^^^^^^^^^^^^^^

It is possible to define Dead Letter Queues for SQS messages (DLQ). It is possible to easily define this in ECS ComposeX
simply by referring to the name of the queue, deployed in this same deployment.

.. warning:: It won't be possible to import a queue ARN at this time in ECS ComposeX that exists outside of the stack today.

Settings
========

No specific settings for SQS at this point.

Services
========

Similar to all other modules, we have a list of dictionaries, with two keys of interest:

* name: the name of the service as defined in services
* access: the type of access to the resource.
* scaling: Allow to define the scaling behaviour of the service based on SQS Approximate Messages Visible.

Access types
^^^^^^^^^^^^^

* RO - read only
* RWMessages - read/write messages on the queue
* RWPermissions - read/write messages and grants access to modify some queue attributes

.. tip::

    IAM policies, are defined in sqs/sqs_perms.json

Lookup
======

Lookup is currently implemented for SQS!

Scaling
=======

You can now defined StepScaling on the ECS Service based on the number of messages in the queue!

.. code-block:: yaml
    :caption: Scaling Syntax

    scaling:
      steps:
        - lower_bound: int
          upper_bound: int
          count: int
      scaling_in_cooldown: int
      scaling_out_cooldown: int


.. note::

    If you already setup other Scaling policies for the service, beware of race conditions!

Examples
========

.. code-block:: yaml
    :caption: Simple SQS Queues with DLQ configured

    x-sqs:
      Queue02:
        Services:
          - name: app02
            access: RWPermissions
          - name: app03
            access: RO
        Properties:
          RedrivePolicy:
            deadLetterTargetArn: Queue01
            maxReceiveCount: 10
        Settings:
          EnvNames:
            - APP_QUEUE
            - AppQueue

      Queue01:
        Services:
          - name: app03
            access: RWMessages
        Properties: {}
        Settings:
          EnvNames:
            - DLQ
            - dlq


.. code-block:: yaml
    :caption: SQS Queue with scaling definition

    x-sqs:
      QueueA:
        Services:
          - name: abcd
            access: RWMessages
            scaling:
              scale_in_cooldown: 120
              scale_out_cooldown: 60
              steps:
                - lower_bound: 0
                  upper_bound: 10
                  count: 1 # Gives you 1 container if there is between 0 and 10 messages in the queue.
                - lower_bound: 10
                  upper_bound: 100
                  count: 10 # Gives you 10 containers if you have between 10 and 100 messages in the queue.
                - lower_bound: 100
                  count: 20 # Gives you 20 containers if there is 100+ messages in the queue

.. note::

    The last step cannot have defined a upper_bound. If you set one, it will be automatically be removed.

.. note::

    You need to have defined x-configs/scaling/range to enable step scaling on the ECS Service.

.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
