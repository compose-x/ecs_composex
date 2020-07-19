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

Features
========

* From docker-compose to AWS ECS
    * Support for EC2 and Fargate deployments (built for Fargate first)
    * One-liner integration for your services to Load-Balancers
    * Automatically configures the Task CPU and RAM requirements.
    * One-liner expansion of your tasks to using AWS X-Ray for distributed tracing.
    * Automatic dependencies and network access control via Security Group rules.

* AWS AppMesh and CloudMap
    * Built-in integration to CloudMap to automatically register your services to Service Discovery
    * Simplified definition of your mesh, routers, nodes and services.

* AWS RDS
    * Simplified syntax to create DBs
    * Automatically creates secret for your database and exposes these to select services via Secrets definition.
    * Allows ECS Services to have TCP access by automatically managing Ingress Rules for AWS Security Groups.

* AWS SQS
    * Create queues and link them to your ECS Services with least-privileges
    * Exposes env vars with the Queue ARN to your ECS tasks
    * Logically link a queue and its DLQ simply referencing it by name.

* AWS SNS
    * Create topics and allow ECS Services to publish messages
    * Create subscriptions from SNS to SQS

And a lot more to come!

Installation
============

.. code-block:: bash

    pip install ecs_composex

Example Usage
==============

.. raw:: html

    <script id="asciicast-ORH1AVrFRJxhRbJdst8X44AqB" src="https://asciinema.org/a/ORH1AVrFRJxhRbJdst8X44AqB.js" async></script>

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


Introduction
============

`Docker Compose`_ has been around for a long while and enabled developers to perform local integration testing between
their microservices as well as with other dependencies their application have (i.e. a redis or MySQL server).

However, for developers to translate their docker compose file into an AWS infrastructure can be a lot of work. And for
the cloud engineers (or DevOps engineers) it can very quickly become something overwhelming to manage at very large scale
to ensure best-practices are in place, for example, ensuring least privileges access from a service to another.

This is where `ECS ComposeX`_ comes into play.

Translate Docker services into AWS ECS
---------------------------------------

First ECS ComposeX translates the services definition in the docker compose file into the ECS definitions to allow the service to
run on AWS. It will, doing so, create all the necessary elements to ensure a successful and feature rich deployment into ECS.

.. note::

    ECS ComposeX has been built to allow services to run with Fargate or EC2.


Provision other AWS resources your services need
-------------------------------------------------

So you have the definitions of your services and they are running on ECS.
But what about these other services that you need for your application to work? DBs, notifications, streams etc.
Are you going to run your MySQL server onto ECS too or are you going to want to use AWS RDS?
How are you going to define the IAM roles and policies for each service? Access Secrets? Configuration settings?

That is the second focus of ECS ComposeX: defining extra sections in the YAML document of your docker compose file, you
can define, for your databases, queues, secrets etc.

ECS ComposeX will parse every single one of these components. These components can exist on their own but what is of interest
is to allow the services to access these.

That is where ECS ComposeX will automatically take care of all of that for you.

For services like SQS or SNS, it will create the IAM policies and assign the permissions to your ECS Task Role so the service
gets access to these via IAM and STS. Credentials will be available through the metadata endpoint, which your SDK will pick
immediately.

For services such as RDS or ElasticCache, it will create the security groups ingress rules as needed, and when applicable,
will handle to generate secrets and expose these via ECS Secrets to your services.

What does ECS ComposeX do differently?
--------------------------------------

Where ECS ComposeX distinguishes itself from other tools is embedding security for each service individually,
so that developers only have to connect resources logically together in the same way they would use links between
microservices in their Docker Compose definition. Each microservice needs to explicitly be declared as a consumer of a
resource to get access to it, otherwise it won’t be able to access the resource or other microservices. This is done
simply by using AWS IAM policies or security groups ingress, where applicable. In a future release, ECS ComposeX will
allow using AWS App Mesh for service-to-service communication. This provides the cloud engineers the peace of mind that
the surface of attack to the platform is limited in distributed environments as isolation is achieved for each
microservice individually.

That simplified way to define access between services and resources helps with defining a shared-responsibility model
between application engineers and cloud engineers. Application engineers must know what their application does and how
services interface to each other and to external services. This gives a sense of ownership to the maintainers of the
Docker Compose file that defines the application stack resources and services along with resources access and
permissions.


Plug-And-Play
--------------

ECS ComposeX allows to create not only the resources your application stack needs, but also the underlying infrastrcuture,
for example, your networking layer (VPC, subnets etc.) as well as the compute (using SpotFleet by default).

This is to allow developers to deploy in their development accounts without having to concern themselves with network
design and capacity planning.

.. note::

    | :ref:`vpc_network_design`
    | :ref:`ec2_compute_design`
    | :ref:`syntax_reference`

.. note::

    If you do not need extra AWS resources such as SQS queues to be created as part of these microservices deployments, I would recommend to use `AWS ECS CLI`_ which does already a lot of the work for the services.
    Alternatively, use the AWS CLI v2. It is absolutely smashing-ly awesome and might be just what you need
    This tool aims to reproduce the original ECS CLI behaviour whilst adding logic for non ECS resources that you want to create in your environment.

Fargate First
-------------

However the original deployments and work on this project was done using EC2 instances (using SpotFleet mostly), everything
is now implemented to work on AWS Fargate First (2020-06-06).

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
