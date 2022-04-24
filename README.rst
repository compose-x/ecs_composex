.. meta::
    :description: ECS Compose-X
    :keywords: AWS, ECS, Fargate, Docker, Containers, Compose, docker-compose

============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE| |PY_DLS|

|CODE_STYLE| |TDD| |BDD|

|QUALITY|

|BUILD|

---------------------------------------------------------------------------------------------------------------
Manage, Configure and deploy your applications/services and AWS resources from your docker-compose definitions
---------------------------------------------------------------------------------------------------------------

Useful Links
===============

* `Documentation`_
* `Blog`_
* `Labs <https://labs.compose-x.io/>`_
* `Feature requests <https://github.com/compose-x/ecs_composex/projects/2>`_
* `Issues <https://github.com/compose-x/ecs_composex/projects/3>`_
* `Compatibility Matrix`_


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

.. code-block:: bash

    pip install ecs-composex


How is it different ?
=====================

There are a lot of similar tools out there, including published by AWS. So here are a few of the features
that we think could be of interest to you.

Modularity / "Plug & Play"
---------------------------

The origin of ECS Compose-X was to provide developers with the ability of deploying an entire test stack from scratch.
However, the reality is more that companies have already gotten VPC/Networking sorted out, other applications, services
and resources already exist and new services need access to that existing infrastructure.

So with ECS-ComposeX we have since very early on , defined `Lookup`_, which allows you to use your existing services
and resources you have in AWS. Via API discovery, all the settings, configuration of those will be used to grant
the necessary access and define configuration accordingly for your services to use these successfully.


Deploy to AWS Fargate, AWS EC2 and ECS Anywhere
---------------------------------------------------

Since the beginning, the focus has been on running with AWS Fargate, as it is what allows developers least effort
to deploying applications. But by users demand, the project was adapted to support deploying to existing EC2 based
clusters, as well as on ECS Anywhere.

With the growing adoption of other ARM there is also now support to specify whether you want to run your services
on AWS Fargate using Graviton processors.

Attributes auto-correct
-------------------------

A fair amount of the time, deployments via AWS CloudFormation, Ansible and other IaC will fail because of incompatible
settings. This is particularly frustrating and can lead to failed deployments.
It happened to us all, a number of times, with a lot of different AWS Services.

Whilst giving you the ability to use all properties of AWS CloudFormation objects, whenever possible, ECS Compose-X
will try to identify incompatible settings, warn you of changes it made, and otherwise fail early to avoid deployment
issues.

For example, if you set the Log retention to be 42 days, which is invalid, it will automatically change that to the
closest valid value (here, 30).

Create your own modules
==========================

Since version 0.18 of ECS Compose-X, you can create your own ``x-`` modules that will automatically be detected at
execution time. Thanks to the module manager, if your module contains all the necessary entrypoints, it will be able
to act as an extension of compose-x and do whatever you want it to do.

See how to create your own modules

Credits
=======

This package would not have been possible without the amazing job done by the AWS CloudFormation team!
This package would not have been possible without the amazing community around `Troposphere`_!

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
.. _Compatibility Matrix: https://nightly.docs.compose-x.io/compatibility/docker_compose.html
.. _Find out how to use ECS Compose-X in AWS here: https://blog.compose-x.io/posts/use-your-docker-compose-files-as-a-cloudformation-template/index.html
.. _Documentation: https://docs.compose-x.io

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

.. |PY_DLS| image:: https://img.shields.io/pypi/dm/ecs-composex
    :target: https://pypi.org/project/ecs-composex/
