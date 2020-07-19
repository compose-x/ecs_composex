============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE|

|CODE_STYLE| |TDD| |BDD| |CODECOV|

|BUILD|

----------------------------------------------------------------------------------------------------
Be for AWS ECS and docker-compose what AWS SAM is to Lambda
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

    sage: ecs_composex [-h] -n NAME -f DOCKERCOMPOSEXFILE
                    [-d OUTPUTDIRECTORY]
                    [--deploy]
                    [--format {json,yaml,text}]
                    [--cfn-config-file CFNCONFIGFILE]
                    [--no-cfn-template-config-file]
                    [--region REGIONNAME]
                    [--az ZONES]
                    [-b BUCKETNAME] [--no-upload]
                    [--create-vpc]
                    [--vpc-cidr VPCCIDR]
                    [--vpc-id VPCID]
                    [--public-subnets PUBLICSUBNETS]
                    [--app-subnets APPSUBNETS]
                    [--storage-subnets STORAGESUBNETS]
                    [--discovery-map-id VPCDISCOVERYMAPID]
                    [--single-nat]
                    [--create-cluster]
                    [--cluster-name ECSCLUSTERNAME]

.. note::

    Each component can also use the docker-compose file but be deployed on its own, allowing, for production workloads,
    to deploy each component separately to avoid dependencies on each other.

AWS Resources support
=====================

* `AWS ECS`_: from docker-compose to ECS transparently, using AWS Fargate primarily.
* `AWS VPC`_: create or use existing VPC to deploy your services
* `AWS AppMesh`_: Services mesh for your services.
* `AWS SQS`_: queues for distributed workloads
* `AWS RDS`_: databases integration made easy
* `AWS EC2`_: Deploy your services on EC2 for custom settings. Features SpotFleet by default.
* AWS SNS



Documentation
=============

`Find all the documentation to get started and all the features references here. <https://docs.ecs-composex.lambda-my-aws.io>`_

.. seealso::

    `Nightly documentation <https://nightly.docs.ecs-composex.lambda-my-aws.io/>`_ following the master branch.


RoadMap
========

* `Feature requests <https://github.com/lambda-my-aws/ecs_composex/projects/2>`_
* `Issues <https://github.com/lambda-my-aws/ecs_composex/projects/3>`_


Blog
====

Follow the news and technical articles on using ECS ComposeX on the `Blog`_

* `CICD Pipeline for multiple services on AWS ECS with ECS ComposeX`_

.. tip::

    If you do not need extra AWS resources such as SQS queues to be created as part of these microservices deployments,
    I would recommend to use `AWS ECS CLI`_ which does already a lot of the work for the services.
    Alternatively, use the AWS CLI v2. It is absolutely smashing-ly awesome and might be just what you need
    This tool aims to reproduce the original ECS CLI behaviour whilst adding logic for non ECS resources that you want
    to create in your environment.



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
.. _ECS ComposeX: https://docs.ecs-composex.lambda-my-aws.io
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
.. _ECS ComposeX Project: https://github.com/orgs/lambda-my-aws/projects/3
.. _CICD Pipeline for multiple services on AWS ECS with ECS ComposeX: https://blog.ecs-composex.lambda-my-aws.io/posts/cicd-pipeline-for-multiple-services-on-aws-ecs-with-ecs-composex/

.. _AWS ECS: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#services
.. _AWS VPC: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#aws-vpc-needs-no-introduction
.. _AWS RDS: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#aws-rds
.. _AWS SQS: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#aws-sqs
.. _AWS EC2: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#ec2-resources-for-ecs-cluster
.. _AWS AppMesh: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#aws-appmesh-aws-cloud-map-for-services-mesh-discovery

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

.. |BLOG_RELEASE| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoicHZaQXFLNGYya3pzWExXM09ZTDZqbkU4cXZENzlZc2grQ0s5RXNxN0tYSXF6U3hJSkZWd3JqZkcrd29RUExmZGw1VXVsTTd6ckE4RjhSenl4QUtUY3I0PSIsIml2UGFyYW1ldGVyU3BlYyI6IjdleGRRTS9rbTRIUUY4TkoiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master
