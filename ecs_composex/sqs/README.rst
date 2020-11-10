.. _aws_sqs_readme:

=======
AWS SQS
=======

This module aims to create the SQS Queues and expose there properties via *AWS CFN exports* so that they can be used and
referenced to/by services stacks to create IAM policies accordingly.

Queue properties
=================

In order to make things very simple, the definition of properties follows the exact pattern as for the `CFN SQS definition`_.

ComposeX Features
=================

Redrive policy
^^^^^^^^^^^^^^

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




.. _CFN SQS definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-sqs-queues.html


.. seealso::

    See :ref:`sqs_syntax_reference`
