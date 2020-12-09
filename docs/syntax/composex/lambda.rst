.. _lambda_syntax_reference:

==============
x-lambda
==============

.. code-block:: yaml

    x-lambda:
      function-01:
        Properties: {}
        MacroParameters: {}
        Services: []
        Settings: {}
        Lookup


Properties
===========

x-lambda will support either AWS::Lambda::Function and AWS::Serverless::Function properties set.

.. tip::

    We recommend to use AWS::Serverless::Function as this makes it a lot easier for yourselves.


Using AWS::Lambda::Function
----------------------------

For Lambda functions defined as such with the "primitive" resource type, ECS ComposeX will automatically create IAM role,
and if set via `Settings`_ Lambda Function and Lambda version, similarly to AWS::Serverless::Function.


Using AWS::Serverless::Function
--------------------------------

Serverless functions are great to simplify syntax and auto-manage a number of things for you.
We won't in ComposeX try to override anything, at most, we will be setting specific VPC and Subnets settings for Lambdas
that might require VPC access to resources, and IAM permissions to other resources.

Some rules and settings apply for all deployments

* If you did set extra resources via AWS::Serverless::Function, such as events, or queues etc, we won't be altering anything.
* If you do not set **Role** nor **Policies** we will automatically create one separately and grant it minimum IAM access.

.. note::

    Using ECS ComposeX to deploy your lambda via defining all the above attributes for either resource type is more something
    implemented to make some integrations easier.

    We still would recommend to rely on much better tools such as AWS SAM to do your lambda functions packaging and release
    the code.

.. warning::

    Using Lookup will allow you to grant your services to invoke lambda functions in an easier fashion but won't alter the existing function settings

Settings
=========

The settings will follow the exact same properties types as AWS::Serverless::Function transform options which are not
present in the AWS::Lambda::Function.


Define your lambda function as a service in your compose file
===============================================================

Naturally, running your lambda function in a docker container locally will make your function behave ever so slightly
differently especially if your code allow to run infinitely, which in Lambda would be terrible!

But, in order to make it easy for you to integrate and deploy your lambda function, we are introducing this feature.

.. code-block:: yaml

    services:
      function-01:
        build:
          context ./path/to/context
          dockerfile: Dockerfile
        command: python main_package.lambda_handler
        x-lambda:
          BucketName: name-of-bucket-to-store-code-to
          Prefix: bucket prefix
          Name: myfunction.zip # Empty will generate a file based on the checksum of code
          CodeSigningConfigArn: String

