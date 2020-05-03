ecs_composex.sqs
================

.. contents::

Services
--------

Similar to all other modules, we have a list of dictionaries, with two keys of interest:

* name: the name of the service as defined in services
* access: the type of access to the resource.

Access types
^^^^^^^^^^^^^

* RO - read only
* RWMessages - read/write messages on the queue
* RWPermissions - read/write messages and grants access to modify some queue attributes

.. tip::

    IAM policies, are defined in sqs/sqs_perms.py


Settings
--------

No specific settings for SQS at this point.


Properties
----------

SQS does not require any properties to be set in order to create the queue. No settings are mandatory.

Special properties
^^^^^^^^^^^^^^^^^^

It is possible to define Dead Letter Queues for SQS messages (DLQ). It is possible to easily define this in ECS ComposeX
simply by referring to the name of the queue, deployed in this same deployment.

.. warning:: It won't be possible to import a queue ARN at this time in ECS ComposeX that exists outside of the stack.

To do so, simply use the following syntax:

Samples
--------

.. code-block:: yaml

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



.. _Engine: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engine
.. _EngineVersion: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-rds-dbcluster.html#cfn-rds-dbcluster-engineversion
