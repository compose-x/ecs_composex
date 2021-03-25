.. meta::
    :description: ECS Compose-X
    :keywords: AWS, ECS, Fargate, Docker, Containers, Compose, docker-compose

============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE|

|CODE_STYLE| |TDD| |BDD|

|QUALITY|

|BUILD|

---------------------------------------------------------------------------------------------------------------
Manage, Configure and deploy your applications/services and AWS resources from your docker-compose definitions
---------------------------------------------------------------------------------------------------------------

Why use ECS Compose-X?
========================

As a developer, working locally is a crucial part of your day to day work, and **docker-compose** allows you to do
just that, for simple services as well as very complex structures.

Your prototype works, and you want to deploy to AWS. But what about IAM ? Networking ? Security ? Configuration ?

Using ECS Compose-X, you keep your docker-compose definitions as they are, add the AWS services you have chosen
as part of that definition, such as ELB, RDS/DynamodDB Databases etc, and the program will automatically
generate all the AWS CloudFormation templates required to deploy all your services.

It automatically takes care of network access requirements and IAM permissions, following best practices.


Installation
============

ECS Compose-X can be used as a CLI ran locally, in CICD pipelines, or as an AWS CloudFormation macro, allowing you
to use your Docker Compose files directly in CloudFormation!

On AWS using AWS CloudFormation Macro
--------------------------------------

You can now deploy the CloudFormation macro to your AWS Account using AWS Serverless Application Repository (SAR).

Deploy it in your account today |AWS_SAR|

.. |AWS_SAR| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://serverlessrepo.aws.amazon.com/applications/eu-west-1/518078317392/compose-x


`Find out how to use ECS Compose-X in AWS here`_

Via pip
--------

.. code-block:: bash

    pip install ecs_composex


CLI Usage
==========

.. code-block:: bash

    usage: ecs-compose-x [-h] {up,render,create,config,init,version} ...

    positional arguments:
      {up,render,create,config,init,version}
                            Command to execute.
        up                  Generates & Validates the CFN templates,
                            Creates/Updates stack in CFN
        render              Generates & Validates the CFN templates locally. No
                            upload to S3
        create              Generates & Validates the CFN templates locally.
                            Uploads files to S3
        config              Merges docker-compose files to provide with the final
                            compose content version
        init                Initializes your AWS Account with prerequisites
                            settings for ECS
        version             ECS ComposeX Version

    optional arguments:
      -h, --help            show this help message and exit


Examples
--------

.. code-block:: bash

    # Render all your CFN templates from your docker compose and extension files
    ecs-compose-x render --format yaml -n my-awesome-app -f docker-compose.yml -f aws.yml -d outputs

    # Deploy / Update your application to AWS
    ecs-compose-x up --format yaml -n my-awesome-app -f docker-compose.yml -f aws.yml -d outputs


Features
=========

AWS Services support
---------------------

* `AWS ECS`_
* `AWS RDS`_
* `AWS DynamoDB`_
* `AWS DocumentDB`_
* `AWS ElastiCache`_
* `AWS S3`_
* `AWS SQS`_
* `AWS Kinesis`_
* `AWS SNS`_
* `AWS ELBv2`_
* `AWS ACM`_
* `AWS AppMesh`_
* `AWS IAM`_
* `AWS KMS`_
* `AWS CloudWatch`_
* `AWS VPC`_
* `AWS EC2`_

To have an extensive list of support, refer to `the compatibilty matrix`_ and the syntax reference for each AWS services
in our `documentation`_

How is it different ?
=====================

There are a lot of similar tools out there, including published by AWS. So here are a few of the features
that we think could be of interest to you.

Modularity / "Plug & Play"
---------------------------

The majority of people who are going to use ECS ComposeX on a daily basis should be developers who need to have an
environment of their own and want to quickly iterate over it.

However, it is certainly something that Cloud Engineers in charge of the AWS accounts etc. would want to use to make their own lives easy too.

In many areas, you as the end-user of ComposeX will already have infrastructure in place: VPC, DBs and what not.
So as much as possible, you will be able in ComposeX to define `Lookup`_ sections which will find your existing resources,
and map these to the services.

Built for AWS Fargate
----------------------

However the original deployments and work on this project was done using EC2 instances (using SpotFleet), everything
is now implemented to work on AWS Fargate First (2020-06-06).

That said, all features that can be supported with EC2 instances are available to you with ECS Compose-X, which, will
simply disable such settings when deployed on top of AWS Fargate.

Attributes auto-correct
-------------------------

A fair amount of the time, deployments via AWS CloudFormation, Ansible and other IaC will fail because of incompatible
settings. This happened a number of times, with a lot of different AWS Services.

Whilst giving you the ability to use all properties of AWS CloudFormation objects, whenever possible, ECS Compose-X
will understand how two services are connected and will auto-correct the settings for you.

For example, if you set the Log retention to be 42 days, which is invalid, it will automatically change that to the
closest valid value (here, 30).

Documentation
=============

Find all the `documentation` to get started and and start deploying to AWS

.. tip::

    `Nightly documentation <https://nightly.docs.compose-x.io/>`_ following the main branch.

RoadMap
========

* `Feature requests <https://github.com/compose-x/ecs_composex/projects/2>`_
* `Issues <https://github.com/compose-x/ecs_composex/projects/3>`_

Blog
====

`Follow the latest publications on our blog <https://blog.compose-x.io>`__

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
.. _Blog: https://blog.compose-x.io/
.. _Docker Compose: https://docs.docker.com/compose/
.. _ECS ComposeX: https://docs.compose-x.io
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
.. _ECS ComposeX Project: https://github.com/orgs/lambda-my-aws/projects/3
.. _CICD Pipeline for multiple services on AWS ECS with ECS ComposeX: https://blog.compose-x.io/posts/cicd-pipeline-for-multiple-services-on-aws-ecs-with-ecs-composex/

.. _AWS ECS:            https://nightly.docs.compose-x.io/syntax/composex/ecs.html
.. _AWS VPC:            https://nightly.docs.compose-x.io/syntax/composex/vpc.html
.. _AWS RDS:            https://nightly.docs.compose-x.io/syntax/composex/rds.html
.. _AWS DynamoDB:       https://nightly.docs.compose-x.io/syntax/composex/dynamodb.html
.. _AWS DocumentDB:     https://nightly.docs.compose-x.io/syntax/composex/docdb.html
.. _AWS ACM:            https://nightly.docs.compose-x.io/syntax/composex/acm.html
.. _AWS ELBv2:          https://nightly.docs.compose-x.io/syntax/composex/elbv2.html
.. _AWS S3:             https://nightly.docs.compose-x.io/syntax/composex/s3.html
.. _AWS IAM:            https://nightly.docs.compose-x.io/syntax/composex/ecs.details/iam.html
.. _AWS Kinesis:        https://nightly.docs.compose-x.io/syntax/composex/kinesis.html
.. _AWS SQS:            https://nightly.docs.compose-x.io/syntax/composex/sqs.html
.. _AWS SNS:            https://nightly.docs.compose-x.io/syntax/composex/sns.html
.. _AWS KMS:            https://nightly.docs.compose-x.io/syntax/composex/kms.html
.. _AWS ElastiCache:    https://nightly.docs.compose-x.io/syntax/composex/elasticache.html
.. _AWS EC2:            https://nightly.docs.compose-x.io/features.html#ec2-resources-for-ecs-cluster
.. _AWS AppMesh:        https://nightly.docs.compose-x.io/readme/appmesh.html
.. _AWS CloudWatch:     https://nightly.docs.compose-x.io/syntax/compose_x/alarms.html
.. _Lookup:             https://nightly.docs.compose-x.io/syntax/compose_x/common.html#lookup
.. _the compatibilty matrix: https://nightly.docs.compose-x.io/compatibility/docker_compose.html
.. _Find out how to use ECS Compose-X in AWS here: https://blog.compose-x.io/posts/use-your-docker-compose-files-as-a-cloudformation-template/index.html
.. _documentation: https://docs.compose-x.io

.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiWjIrbSsvdC9jZzVDZ3N5dVNiMlJCOUZ4M0FQNFZQeXRtVmtQbWIybUZ1ZmV4NVJEdG9yZURXMk5SVVFYUjEwYXpxUWV1Y0ZaOEcwWS80M0pBSkVYQjg0PSIsIml2UGFyYW1ldGVyU3BlYyI6Ik1rT0NaR05yZHpTMklCT0MiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main

.. |PYPI_VERSION| image:: https://img.shields.io/pypi/v/ecs_composex.svg
        :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_DL| image:: https://img.shields.io/pypi/dm/ecs_composex
    :alt: PyPI - Downloads
    :target: https://pypi.python.org/pypi/ecs_composex

.. |PYPI_LICENSE| image:: https://img.shields.io/pypi/l/ecs_composex
    :alt: PyPI - License
    :target: https://github.com/compose-x/ecs_composex/blob/master/LICENSE

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

.. |QUALITY| image:: https://sonarcloud.io/api/project_badges/measure?project=compose-x_ecs_composex&metric=alert_status
    :alt: Code scan with SonarCloud
    :target: https://sonarcloud.io/dashboard?id=compose-x_ecs_composex
