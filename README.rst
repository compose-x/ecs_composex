============
ECS ComposeX
============

.. image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiQmdmZGZ3MkJCbDNhYVJvc0oza1orVW4zRjM1N21rdERiZ0NqUXYvSDFXM1Nxb1ROYnJTdDBLc3N3L0FGdm9LVjVkUTlzQkhjR1hZZ2JOTG1GYXB1QTJjPSIsIml2UGFyYW1ldGVyU3BlYyI6Ik5xTGhESjY1ZzVsQ3R4RFMiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master

.. image:: https://img.shields.io/pypi/v/ecs_composex.svg
        :target: https://pypi.python.org/pypi/ecs_composex


.. image:: https://readthedocs.org/projects/ecs-composex/badge/?version=latest
        :target: https://ecs-composex.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. contents::

What is it?
============

ECS ComposeX is a tool to generate CFN templates (using the excellent `Troposphere`_ library) which are going to allow
any developer or cloud engineer to build and publish their applications running in Docker containers on top of AWS ECS.

Once the templates are generated, you can simply create new stacks, in any AWS region, in any AWS Account, seamlessly.

ECS ComposeX aims to be a CLI tool at first for people to run from their laptops or even from their CI/CD pipelines.
Given its nature, it is easy to integrate it into AWS Lambda as a library and enable calling upon it to generate all
the things from there.


What you do with it
===================

1. Take an existing Docker compose file of your services you want to deploy to AWS
2. Add settings to explain how you want to deploy these services
3. Add x- sections for extra AWS Resources you want your services to access to perform their tasks
4. Run ECS ComposeX against your ComposeX file
5. Deploy


Features
========

* Generates all the IAM policies and roles for your microservices to access your extra resources
    * ECS Task Role and policies. Policies are tailored to allow access to only the necessary resources
    * ECS Execution Role and policies, allows ECS-Agent to do its job on your behalf
* Generates the task and service definition based on configuration set in your Docker compose file
    * Task definition with all defined environment variables
    * Add predefined variables from Queues, Topics etc. to allow quick lookup of your resources (ie QueueURL, QueueARN)
    * Service definition with all extra configuration to work with AWS CloudMap or AWS LoadBalancers
* Deploy onto an ECS Cluster
    * Use AWS Fargate with no effort in configuration (Default)
    * Use AWS EC2 SpotFleet if you need hosts control but wan to keep costs under control (optional)
* Generate the VPC you need to support all the network resources with a predefined 3-Tier layout if you need one
    * VPC
    * Subnets (Using the usual 3-Tiers design, Public/App/Storage)
* Generate only the launch-templates for your hosts and run your containers on EC2 from the template with no effort
* Monitor all your microservices via AWS CloudWatch (Logs and metrics)

.. note::

    If you do not need extra AWS resources such as SQS queues to be created as part of these microservices deployments, I would recommend to use `AWS ECS CLI`_ which does already a lot of the work for the services.
    Alternatively, use the AWS CLI v2. It is absolutely smashing-ly awesome and might be just what you need
    This tool aims to reproduce the original ECS CLI behaviour whilst adding logic for non ECS resources that you want to create in your environment.


AWS Account settings and requirements
=====================================

Because of my adhesion to using the Cloud Provider's tools for monitoring, logging, etc, some features and options
are enabled and you would get CloudFormation complain about account level settings not being enabled.

Depending on how you are setting up your AWS account(s) you might have to activate these settings if you haven't already.

.. note::

    It is important that you enable AWS VPC Trunking to allow each service tasks to run within the same SecurityGroup and use the extended number of ENIs per instance.
    Reference: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-instance-eni.html
    Announcement: https://aws.amazon.com/about-aws/whats-new/2019/06/Amazon-ECS-Improves-ENI-Density-Limits-for-awsvpc-Networking-Mode/
    

ECS Settings
-------------

ECS Account settings can be found at https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-account-settings.html

* ECS - VPC Trunking
* ECS Extended logs and monitoring

.. code-block:: bash

    aws ecs put-account-setting --name awsvpcTrunking --value enabled
    aws ecs put-account-setting --name serviceLongArnFormat --value enabled
    aws ecs put-account-setting --name taskLongArnFormat --value enabled
    aws ecs put-account-setting --name containerInstanceLongArnFormat --value enabled
    aws ecs put-account-setting --name containerInsights --value enabled

If you have multiple profiles and use awsume you could iterate over each account and run the above commands to apply it
for your profiles as you switch to them.

.. warning::

    If you do not do that as the root user of the account, you will have to enable that for IAM users or roles specifically.
    A Role/Group/User can have an IAM policy allowing them to put the ecs account settings, but then these settings will only
    apply to the role / user that ran the command.


Why though?
===========

Many companies I have worked with struggle with providing a true cloudy experience to their developers and enable them to deploy AWS resources in a controled fashion.
And when they do give poweruser/administrator level of permissions to the developers, they usually have not been trained approprately to understand fundamentals,
such as least privileges and you end up with services which all use the same AWS Access and Secret keys (yes, I witnessed it recently) and these keys stay around for
eternity (seen 1000+ days).
As an AWS Cloud Engineer, this scares the hell out of me and I feel like this is the first thing I need to fix.
As an automation engineer, I wanted a tool that allows developers to keep using Docker compose, as they very often do, so they can't run their workload on their
laptops for quick testing and application testing.
But, "It works on my laptop" is something that in 2020 is simply unacceptable to companies deploying microservices.

Therefore, combining my love for least privileges and therefore IAM instance capability to implement it, and the need for a tool going these extra miles,
I decided to simply go for it.

.. _later on:

A lot of you probably would prefer to use some other tools, such as Terraform, but I all heartily believe that cloud
engineers should use the IaC provided by the Cloud provider. Third party integrations are coming, including for example
the excellent AWS CFN registries where we already see partners like DataDog provide the ability to create non AWS
resources as part of the CFN stack and remove the need for custom made code.


Why am I not using AWS CDK?
===========================

I started this work before AWS CDK came out with any python support, and I am not a developer professionally but I do love developing, and python is my language
of choice. Troposphere was the obvious choice as the python library to use to build all the CFN templates. I find the way Troposphere has been built is awesome,
it has a very nice community and is released often. I did a few PRs myself and `Mark Peek`_ is very proactive with PRs, releases come out often.

Will I use CDK in the future? Depends on how many of you are going to use ECS ComposeX and will ask for it.


Why not stick to AWS CFN Templates and CFN macros ?
====================================================

I love CFN Macros and I think that it is not enough spoken about. Probably because at start, Fn::Transform was not over
well documented and importing snippets wasn't working all the time as one would have wanted.

I love CFN and I can write templates very easily in YAML or even in JSON. But, typos are a nightmare and it takes a good
IDE configuration to make it easy and viable. For small templates, it is fine, but with a lot of conditions, references,
parameters, imports, it is very easy to mess it up. And when come nested stacks, it is a huge amount of time spent waiting
and hoping nothing wrong happens in a nested stack.

So, using python, I can do all the loops I want, and most importantly, I can make super consistent all the titles for
the various AWS resources that the templates are going to create. If I make a typo somewhere in a title, this typo goes everywhere,
and therefore, AWS CFN is happy to resolve, find, GetAttributes etc from it.

This saves an insane amount of time.

Also, thanks to using Python and with YAML as a common syntax method to write Docker compose files and AWS templates, we
can marry the two very easily.


I want to use EKS. Can I use ECS ComposeX?
==========================================

You certainly could, but you wouldn't really, or maybe only for the IAM part? If you plan on using EKS, I can't recommend enough to use the AWS
Service Operator for K8s. You can refer to this blog https://aws.amazon.com/blogs/opensource/aws-service-operator-kubernetes-available/ to get more details
about it. You will notice a lot of similarities in what ECS ComposeX tries to achieve, but for ECS as opposed to EKS.


What is next for ECS ComposeX ?
===============================

* CI/CD for everyone so that any PR is evaluated automatically and possibly merged
* Add more resources supports (DynamoDB tables, SNS Topics, and then RDS).
* Enable definition of AppMesh routes from the Docker compose file (gotta dig more into this)
* Allow to add x-lambdas which would go through git/folder based discovery of existing functions written with SAM and
  identify resources to be shared(ie, queue between ECS service and a Lambda).
* Architecture reference for usage in CI/CD

First, move this into a CFN Macro, with a simple root template that would take a few settings in and the URL to the Compose file and render all templates within CFN itself via Lambda.
Then, with the newly released CFN Private Registries, mutate this system to have fully integrated to CFN objects which will resolve all this.


License and documentation
==========================

* Free software: BSD license
* Documentation:
    * https://docs.ecs-composex.lambda-my-aws.io
    * https://ecs-composex.readthedocs.io/en/latest


Credits
=======

This package would not have been possible without the amazing job done by the AWS CloudFormation team!

This package would not have been possible without the amazing community around `Troposphere`_!


This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

Disclaimer
===========

* I am not an AWS employee
* I am not being paid by AWS
* I don't even have AWS shares ..
* I don't intend to sell anything to anyone
* I am doing this on my free time because I like doing some functional coding/scriping
* I am in no way an prod-ready app developer so I am sure a lot of stuff is not the most optimal with my code. PRs welcome.
* I come learning C in such a way that each function can't be longer than 25 lines, 80 chars wide and 5 functions per file.
  This obviously is not so realistic in python, but I try to keep my code clean and the function names as clear as possible.


.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`Mark Peek`: https://github.com/markpeek
.. _`AWS ECS CLI`: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_CLI.html
.. _Troposphere: https://github.com/cloudtools/troposphere
