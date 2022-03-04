
.. meta::
    :description: ECS Compose-X How To
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, examples


====================================================
Create ECS Scheduled tasks using AWS EventsBridge
====================================================

When using ECS Compose-X, the default assumption is that you want a service that will be managed as such by ECS.
However sometimes, applications do not need to run 24/7 and could scale appropriately based on an event, managed
by `AWS EventsBridge`_.


Let's take a couple use-cases.


Batch Processing based on time event
--------------------------------------

This is a rather common use-case. Although sometimes people prefer to go with an AWS Lambda Function to do this,
ECS can offer significant benefits over Lambda.

So say your docker-compose file had the following definition

.. code-block:: yaml

    services:
      web-application:
        image: my-web-app

      batch-processing:
        image: my-batch-app

By default, compose-x would create an ECS Service for both the web-application and batch-processing services.

Let's assume that you need processing data every day at a given time, you would not need the batch-processing running
at any other time. So, to tell ECS Compose-X to do that, we add the following snippet to the code

.. code-block:: yaml

    x-events:
      daily:
        Properties:
          Description: "example event triggered ECS"
          Name: "batch-application example"
          ScheduleExpression: "rate(12 hours)"
        Services:
          - name: batch-processing
            TaskCount: 3
            DeleteDefaultService: True

.. note::

    In the above snippet, note **DeleteDefaultService** is set to true:
    this instructs not to create an ECS Service, and only a Task Definition.



Start processes based on AWS Services events
-----------------------------------------------

Similar to the previous example, we now want to use an AWS Event that we filter out with Events Bridge.
Let's take an example from the `AWS CFN documentation page for Event Rule`_


.. code-block:: yaml

    EventRule:
      Type: AWS::Events::Rule
      Properties:
        Description: "EventRule"
        EventPattern:
          source:
            - "aws.ec2"
          detail-type:
            - "EC2 Instance State-change Notification"
          detail:
            state:
              - "stopping"
        State: "ENABLED"
        Targets:
          -
            Arn:
              Fn::GetAtt:
                - "LambdaFunction"
                - "Arn"
            Id: "TargetFunctionV1"



Let's say, instead of going to Lambda, we want to invoke our container to execute a script which might be more effective
running inside a container.

Here is what the transformed adaptation would look like.

.. code-block:: yaml

    services:
      ec2-stopping-cleanup: {}

    x-events:
      EventRule:
        Properties:
          Description: "EventRule"
          EventPattern:
            source:
                - "aws.ec2"
            detail-type:
                - "EC2 Instance State-change Notification"
            detail:
                state:
                  - "stopping"
          State: "ENABLED"

        Services:
          - name: ec2-stopping-cleanup
            TaskCount: 3
            DeleteDefaultService: True

We removed the **Targets** part of the definition, and now ECS Compose-X will automatically create properties
to use for the event. It will also take care of all the IAM permissions to allow EventBridge to invoke the ECS Service.

And that's it, as simple as that.

A friendly advice when using events
--------------------------------------

Whilst very useful, and can be used in many contexts, I would recommend **not** to use events for S3 files changes:
when you capture a new / updated file event in S3, and start a container, it is started without any context as to what happened,
and you need to implement logic in code to identify "why was the service started".

I would much more recommend to have S3 events that you want to start the containers for in order to perform their tasks,
out of SQS: from S3, funnel your messages to SQS, and start your ECS Services from there (see x-sqs.Scaling).
When the SQS worker on your container will receive the event, it will contain all the details about the file itself.

Now, if you are confident that Lambda can do the processing for you, get lambda to trigger from S3 notifications,
and set SQS as the Lambda DLQ for failed processing.

PS: The lack of event context is true for S3, as it is for any other content. You have to implement the logic yourself.


.. _AWS EventsBridge: https://aws.amazon.com/eventbridge/
.. _AWS CFN documentation page for Event Rule: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-events-rule.html#aws-resource-events-rule-syntax
