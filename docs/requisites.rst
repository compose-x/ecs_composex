.. highlight:: shell

=============
Requirements
=============

To use ECS Compose-X, you must use python3.6+ and have an AWS Account. To run commands locally, you will need
permissions to validate the templates with AWS CloudFormation, along with more features, such as Lookup.

AWS Account configuration
==========================

We recommend to have your local profile (if running in EC2/Codebuild, set the IAM role accordingly), as described below.

IAM Permissions to use ECS Compose-X Lookup
---------------------------------------------

To perform Lookup on your resources, such as VPC, ECS Cluster, RDS etc, and to use all the functionalities
in ECS Compose-X, we highly recommend to use the managed policy **arn:aws:iam:aws::policy/ReadOnlyAccess**
which will ``Allow`` do List, Describe resources and their settings.

.. hint::

    Although most resources Lookup depend on tagging, some resources needed discovery with their native API.
    Some other resources, when supported, will use the Cloud Control API to retrieve their properties.


For cloudformation deployments, we recommend to use an IAM role on the stack that would have ``PowerUser`` policy.
See an example of the `IAM roles we recommend for CICD here.`_


Permissions to upload files to S3
----------------------------------

Given that nested stacks need their own templates to be stored in S3, when using `ecs-compose-x` commands ``up``, ``plan``, ``create``,
you will need to have permissions to upload the files into a S3 bucket. You can specify an existing bucket with ``-b/--bucket`` on the
command line.

.. tip::

    If you run ``ecs-compose-x init``, a new S3 bucket will automatically be created and used when running subsequent
    compose-x commands.

AWS ECS Settings
-------------------

In order to use all features, especially using the ``awsvpc`` networking mode, required with Fargate(and recommended for EC2),
you need to enable these settings in your account.

.. note::

    It is important that you enable AWS VPC Trunking to allow each service tasks to run within the same SecurityGroup and use the extended number of ENIs per instance.
    Reference: `Container ENI`_
    Announcement: `AWS VPC mode`_


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

    If you want to enable these settings for a specific IAM role you can assume yourself, from CLI you can use ``aws ecs put-account-setting`` as opposed to ``aws ecs put-account-setting-default``

    .. code-block:: bash

        aws ecs put-account-setting --name awsvpcTrunking --value enabled
        aws ecs put-account-setting --name serviceLongArnFormat --value enabled
        aws ecs put-account-setting --name taskLongArnFormat --value enabled
        aws ecs put-account-setting --name containerInstanceLongArnFormat --value enabled
        aws ecs put-account-setting --name containerInsights --value enabled


.. _IAM roles we recommend for CICD here.: https://github.com/compose-x/codepipline-orchestra/blob/main/aws_accounts_setup/templates/cicd_iam_roles.template
.. _Container ENI: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-instance-eni.html
.. _AWS VPC mode: https://aws.amazon.com/about-aws/whats-new/2019/06/Amazon-ECS-Improves-ENI-Density-Limits-for-awsvpc-Networking-Mode
