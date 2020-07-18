============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE|

|CODE_STYLE| |TDD| |BDD| |CODECOV|

|BUILD|

----------------------------------------------------------------------------------------------------
Build your infrastructure and deploy your services to AWS services using docker-compose file format.
----------------------------------------------------------------------------------------------------

.. contents::
    :local:
    :depth: 1

Installation
============

.. code-block:: bash

    pip install ecs_composex

Usage
=====

.. code-block:: bash

    sage: ecs_composex [-h] -n NAME -f DOCKERCOMPOSEXFILE [-d OUTPUTDIRECTORY]
                    [--format {json,yaml,text}]
                    [--cfn-config-file CFNCONFIGFILE]
                    [--no-cfn-template-config-file] [--region REGIONNAME]
                    [--az ZONES] [-b BUCKETNAME] [--no-upload] [--create-vpc]
                    [--vpc-cidr VPCCIDR] [--vpc-id VPCID]
                    [--public-subnets PUBLICSUBNETS]
                    [--app-subnets APPSUBNETS]
                    [--storage-subnets STORAGESUBNETS]
                    [--discovery-map-id VPCDISCOVERYMAPID] [--single-nat]
                    [--create-cluster] [--cluster-name ECSCLUSTERNAME]
                    [--use-spot-fleet]
                    [_ [_ ...]]

Features
========

* AWS ECS & EC2 components
    * Support for EC2 and Fargate deployments (built for Fargate first)
    * One-liner integration for your services to Load-Balancers
    * Automatically configures the Task CPU and RAM requirements.
    * One-liner expansion of your tasks to using AWS X-Ray for distributed tracing.
    * Automatic dependencies and network access control via Security Group rules.

* AWS AppMesh and CloudMap
    * Built-in integration to CloudMap to automatically register your services to Service Discovery
    * Simplified definition of your mesh, routers, nodes and services.

* AWS RDS via *x-rds*
    * Simplified syntax to create DBs
    * Automatically creates secret for your database and exposes these to select services via Secrets definition.
    * Allows ECS Services to have TCP access by automatically managing Ingress Rules for AWS Security Groups.

* AWS SQS *via x-sqs*
    * Create queues and link them to your ECS Services with least-privileges
    * Exposes env vars with the Queue ARN to your ECS tasks
    * Logically link a queue and its DLQ simply referencing it by name.

* AWS SNS *via x-sns*
    * Create topics and allow ECS Services to publish messages
    * Create subscriptions from SNS to SQS

.. note::

    Each component can also use the docker-compose file but be deployed on its own, allowing, for production workloads,
    to deploy each component separately to avoid dependencies on each other.

And a lot more to come!

Fargate First
-------------

However the original deployments and work on this project was done using EC2 instances (using SpotFleet mostly), everything
is now implemented to work on AWS Fargate First (2020-06-06).

Plug-And-Play
--------------

ECS ComposeX allows to create not only the resources your application stack needs, but also the underlying infrastrcuture,
for example, your networking layer (VPC, subnets etc.) as well as the compute (using SpotFleet by default).

This is to allow developers to deploy in their development accounts without having to worry about network
design and capacity planning.

.. note::

    | :ref:`vpc_network_design`
    | :ref:`ec2_compute_design`
    | :ref:`syntax_reference`

.. note::

    If you do not need extra AWS resources such as SQS queues to be created as part of these microservices deployments, I would recommend to use `AWS ECS CLI`_ which does already a lot of the work for the services.
    Alternatively, use the AWS CLI v2. It is absolutely smashing-ly awesome and might be just what you need
    This tool aims to reproduce the original ECS CLI behaviour whilst adding logic for non ECS resources that you want to create in your environment.

License and documentation
==========================

* Free software: GPLv3+
* Documentation:
    * https://docs.ecs-composex.lambda-my-aws.io

Blog
====

.. |BLOG_RELEASE| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoicHZaQXFLNGYya3pzWExXM09ZTDZqbkU4cXZENzlZc2grQ0s5RXNxN0tYSXF6U3hJSkZWd3JqZkcrd29RUExmZGw1VXVsTTd6ckE4RjhSenl4QUtUY3I0PSIsIml2UGFyYW1ldGVyU3BlYyI6IjdleGRRTS9rbTRIUUY4TkoiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master

Follow the news and technical articles on using ECS ComposeX on the `Blog`_ |BLOG_RELEASE|

* `CICD Pipeline for multiple services on AWS ECS with ECS ComposeX`_


GitHub project
==============

To follow the progress of ECS ComposeX and raise issues/feature requests, you can go to to the `ECS ComposeX Project`_


What is next for ECS ComposeX ?
===============================

* Add more resources supports (DynamoDB tables, SNS Topics).
* Enable definition of service mesh and service discovery

First, move this into a CFN Macro, with a simple root template that would take a few settings in and the URL to the Compose file and render all templates within CFN itself via Lambda.
Then, with the newly released CFN Private Registries, mutate this system to have fully integrated to CFN objects which will resolve all this.


Credits
=======

This package would not have been possible without the amazing job done by the AWS CloudFormation team!
This package would not have been possible without the amazing community around `Troposphere`_!
This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _`Mark Peek`: https://github.com/markpeek
.. _`AWS ECS CLI`: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ECS_CLI.html
.. _Troposphere: https://github.com/cloudtools/troposphere
.. _Blog: https://blog.ecs-composex.lambda-my-aws.io/
.. _Docker Compose: https://docs.docker.com/compose/
.. _ECS ComposeX: https://github.com/lambda-my-aws/ecs_composex
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
.. _ECS ComposeX Project: https://github.com/orgs/lambda-my-aws/projects/3
.. _CICD Pipeline for multiple services on AWS ECS with ECS ComposeX: https://blog.ecs-composex.lambda-my-aws.io/posts/cicd-pipeline-for-multiple-services-on-aws-ecs-with-ecs-composex/

.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoidThwNXVIKzVvSnlXcUNVRzVlNE5wN0FiWE4rYzYvaHRNMEM0ZHMxeXRLMytSanhsckozVEN3L1Y5Szl5ZEdJVGxXVElyalZmaFVzR2tSbDBHeFI5cHBRPSIsIml2UGFyYW1ldGVyU3BlYyI6IlZkaml2d28wSGR1YU1xb2ciLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master

.. |DOCS_BUILD| image:: https://readthedocs.org/projects/ecs-composex/badge/?version=latest
        :target: https://ecs-composex.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. |PYPI_VERSION| image:: https://img.shields.io/pypi/v/ecs_composex.svg
        :target: https://pypi.python.org/pypi/ecs_composex


.. |CODECOV| image:: https://img.shields.io/codecov/c/github/lambda-my-aws/ecs_composex?color=black&style=flat-square
    :alt: Codecov
    :target: https://codecov.io/gh/lambda-my-aws/ecs_composex

.. |PYPI_DL| image:: https://img.shields.io/pypi/dm/ecs_composex
    :alt: PyPI - Downloads
    :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_LICENSE| image:: https://img.shields.io/github/license/lambda-my-aws/ecs_composex
    :alt: GitHub
    :target: https://github.com/lambda-my-aws/ecs_composex/blob/master/LICENSE

.. |PYPI_PYVERS| image:: https://img.shields.io/pypi/pyversions/ecs_composex
    :alt: PyPI - Python Version
    :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_WHEEL| image:: https://img.shields.io/pypi/wheel/ecs_composex
    :alt: PyPI - Wheel
    :target: https://pypi.python.org/pypi/ecs_composex

.. |CODE_STYLE| image:: https://img.shields.io/badge/codestyle-black-black
    :alt: CodeStyle
    :target: https://pypi.org/project/black/

.. |TDD| image:: https://img.shields.io/badge/tdd-pytest-black
    :alt: TDD with pytest
    :target: https://docs.pytest.org/en/latest/contents.html

.. |BDD| image:: https://img.shields.io/badge/bdd-behave-black
    :alt: BDD with Behave
    :target: https://behave.readthedocs.io/en/latest/
