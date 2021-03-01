.. meta::
    :description: ECS Compose-X AWS SQS syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS SQS, queuing, messages

.. _sqs_syntax_reference:

======
x-sqs
======

----------------------------------------------------------------------------
Define your AWS SQS Queues and service scaling based on messages queue depth
----------------------------------------------------------------------------

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
--------------------

SQS does not require any properties to be set in order to create the queue. No settings are mandatory.

Special properties
------------------

It is possible to define Dead Letter Queues for SQS messages (DLQ). It is possible to easily define this in ECS ComposeX
simply by referring to the name of the queue, deployed in this same deployment.

.. warning:: It won't be possible to import a queue ARN at this time in ECS ComposeX that exists outside of the stack today.


Services
========

Similar to all other modules, we have a list of dictionaries, with two keys of interest:

* name: the name of the service as defined in services
* access: the type of access to the resource.
* scaling: Allow to define the scaling behaviour of the service based on SQS Approximate Messages Visible.

IAM Permissions
----------------

* RO - read only
* RWMessages - read/write messages on the queue
* RWPermissions - read/write messages and grants access to modify some queue attributes

.. tip::

    IAM policies, are defined in sqs/sqs_perms.json

.. hint::

    You can also use AWS SAM Permissions as defined in `AWS Documentation <https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html>`__

    .. code-block:: yaml
        :caption: SAM Policy Example

        services:
          serviceA: {}
        x-sqs:
          QueueA:
            Services:
              - name: serviceA
                access: SQSPollerPolicy

Lookup
======

See :ref:`lookup_syntax_reference` for more details about Lookup.

.. code-block:: yaml

    x-sqs:
      QueueA:
        Lookup:
          Tags:
            - Name: queue-a-123
            - owner: app01

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


.. tip::

    You can define scaling rules on SQS Queues that you are importing via `Lookup`_

.. attention::

    If you already setup other Scaling policies for the service, beware of race conditions!

Special Features
=================

Redrive policy
--------------

The redrive policy works exactly as you would expect it and is defined in the exact same way as for within
the SQS proprties. Only, here, you only need to put the queue name of the DLQ. The generated ARN etc. will be
fetched via exports (which also implicitly adds a lock on it).

Example with DLQ:

.. code-block:: yaml

    x-sqs:
      DLQ:
        Properties: {}
        Settings: {}
        Services: []

    AppQueue:
      Properties:
        RedrivePolicy:
          deadLetterTargetArn: DLQ
          maxReceiveCount: 10
      Settings:
        EnvNames:
          - APPQUEUE01


Settings
===========

Refer to :ref:`settings_syntax_reference`

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
              ScaleInCooldown: 120
              ScaleOutCooldown: 60
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

    You need to have defined x-configs/scaling/Range to enable step scaling on the ECS Service.

.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
