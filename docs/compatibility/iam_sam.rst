.. _sam_policies_compatibily:

AWS IAM Policies from AWS SAM
==============================

ECS Compose-X has defined some IAM permissions for each resource types. In order to provide developers with greater
flexibility and use well known system, Compose-X also imports IAM definitions from AWS Serverless Application Model.

You can find `all the policies define in AWS SAM in AWS Documentation pages`_.

.. _all the policies define in AWS SAM in AWS Documentation pages: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html


Example
--------

.. code-block:: yaml
    :caption: ECS Compose-X Policy for SQS

    services:
      QueueConsumer: {} # Service definition

    x-sqs:
      QueueA:
        Services:
          - name: QueueConsumer
            access: RWMessages

.. code-block:: yaml
    :caption: Using AWS SAM Policy

    services:
      QueueConsumer: {} # Service definition

    x-sqs:
      QueueA:
        Services:
          - name: QueueConsumer
            access: SQSPollerPolicy

In the example above, we are using the **SQSPollerPolicy** which is already defined for us by AWS SAM.
