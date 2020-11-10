.. highlight:: shell

=============
Requirements
=============

AWS Account configuration
==========================

IAM Permissions to execute ECS ComposeX
----------------------------------------

Since ECS ComposeX adds more and more features, we highly recommend to use the AWS Managed policy
**arn:aws:iam:aws::policy/ReadOnlyAccess**.

Additionally, you will need to use all the features and push your files to S3

.. literalinclude:: composex_iam_policy.json
    :language: json
    :caption: ECS ComposeX specific permissions


ECS Settings
------------

Because of my adhesion to using the Cloud Provider's tools for monitoring, logging, etc, some features and options
are enabled and you would get CloudFormation complain about account level settings not being enabled.

Depending on how you are setting up your AWS account(s) you might have to activate these settings if you haven't already.

.. note::

    It is important that you enable AWS VPC Trunking to allow each service tasks to run within the same SecurityGroup and use the extended number of ENIs per instance.
    Reference: `Container ENI <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-instance-eni.html>`_
    Announcement: `AWS VPC mode <https://aws.amazon.com/about-aws/whats-new/2019/06/Amazon-ECS-Improves-ENI-Density-Limits-for-awsvpc-Networking-Mode/>`_


ECS Account settings can be found at https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-account-settings.html

* ECS - VPC Trunking
* ECS Extended logs and monitoring

.. tip::

    You can now simply run **ecs-composex init** in order to do all of the following and create your default S3 bucket
    for your CFN templates

    .. code-block:: bash

        ecs-composex init


Deploy manually
+++++++++++++++

.. code-block:: bash

    aws ecs put-account-setting-default --name awsvpcTrunking --value enabled
    aws ecs put-account-setting-default --name serviceLongArnFormat --value enabled
    aws ecs put-account-setting-default --name taskLongArnFormat --value enabled
    aws ecs put-account-setting-default --name containerInstanceLongArnFormat --value enabled
    aws ecs put-account-setting-default --name containerInsights --value enabled


.. hint::

    If you want to enable these settings for a specific IAM role you can assume yourself, from CLI you can use `aws ecs put-account-setting` as opposed to `aws ecs put-account-setting-default`

    .. code-block:: bash

        aws ecs put-account-setting --name awsvpcTrunking --value enabled
        aws ecs put-account-setting --name serviceLongArnFormat --value enabled
        aws ecs put-account-setting --name taskLongArnFormat --value enabled
        aws ecs put-account-setting --name containerInstanceLongArnFormat --value enabled
        aws ecs put-account-setting --name containerInsights --value enabled
