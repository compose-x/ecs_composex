.. meta::
    :description: ECS Compose-X macro
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, install, setup


=============================================
ECS Compose-X as an AWS CloudFormation Macro
=============================================

.. include:: macro_install.rst


Use with an existing docker-compose file
=========================================

Say you already have a docker-compose file, and you would like to re-use it as a CloudFormation template.
Well you now can, with the CloudFormation macro for ECS Compose-X.

Now, AWS CloudFormation would try to evaluate everything in your current file, which has neither resources, or parameters etc.
So this is not a valid CloudFormation template.

For that to work though, all you have to do is add the following lines to your template

.. code-block:: yaml

    Transform:
      - compose-x

From there, you can deploy your template from the AWS Console or from the CLI, for example, as shown below

.. code-block:: bash

    CAPABILITIES="APABILITY_AUTO_EXPAND CAPABILITY_IAM CAPABILITY_NAMED_IAM"
    aws cloudformation create-stack --template-body file://merged.yml --capabilities ${CAPABILITIES} --stack-name macro-demo


.. hint::

    If you have multiple docker-compose files you wish to use, you can either do so via `Use with files stored in AWS S3`_
    or simply merge the multiple YAML files together.

Use with files stored in AWS S3
================================

If you have multiple files and through CICD or otherwise, and decided to store them in AWS S3, you can then re-use these
files directly from there.

.. code-block:: yaml

    Fn::Transform:
      Name: compose-x
      Parameters:
        ComposeFiles:
          - s3://files.compose-x.io/docker-compose.yml
          - s3://files.compose-x.io/aws.yml

.. attention::

    Just like with the CLI, the order in which the files are composed together (first file least priority, last highest priority)
    the order you list files in **ComposeFiles** matters in the same way.


Customize to your needs or requirements
========================================

The provided templates that will allow you to create the Lambda function for the macro and the macro itself, requires
an IAM role. Given all the features supported by ECS Compose-X you might want to customize the IAM permissions of the
IAM role assigned to the Lambda function.

The current IAM permissions are permissive to gather any information in the account in order to use the *Lookup** feature.

Using multi-account lookup

If you wish to use the :ref:`lookup_syntax_reference` feature, this is totally possible. Simply ensure that your docker-compose
file indicates which **RoleArn** to use for the specific lookup and adapt the IAM role of the Lambda function role to allow
**sts:AssumeRole** on that role ARN you are indicating.


Current Limitations
=====================

environment files (env_files)
------------------------------

Because of the nature of the syntax requirement for env_files, these are not supported to work with the CFN macro, as the
files are not present in the local filesystem.
