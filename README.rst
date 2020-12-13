============
ECS ComposeX
============

|PYPI_VERSION| |PYPI_LICENSE|

|CODE_STYLE| |TDD| |BDD|

|QUALITY|

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

    usage: ecs-composex [-h] {up,render,create,config,init,version} ...

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



CLI for `up` and `render`

.. code-block:: bash

    usage: ecs_composex up [-h] -n NAME -f DOCKERCOMPOSEXFILE [-d OUTPUTDIRECTORY]
                           [--format {json,yaml,text}] [--region REGIONNAME]
                           [--az ZONES] [-b BUCKETNAME] [--use-spot-fleet]

    optional arguments:
      -h, --help            show this help message and exit
      -n NAME, --name NAME  Name of your stack
      -f DOCKERCOMPOSEXFILE, --docker-compose-file DOCKERCOMPOSEXFILE
                            Path to the Docker compose file
      -d OUTPUTDIRECTORY, --output-dir OUTPUTDIRECTORY
                            Output directory to write all the templates to.
      --format {json,yaml,text}
                            Defines the format you want to use.
      --region REGIONNAME   Specify the region you want to build fordefault use
                            default region from config or environment vars
      --az ZONES            List AZs you want to deploy to specifically within the
                            region
      -b BUCKETNAME, --bucket-name BUCKETNAME
                            Bucket name to upload the templates to
      --use-spot-fleet      Runs spotfleet for EC2. If used in combination of
                            --use-fargate, it will create an additional SpotFleet


CLI for `config`

.. code-block:: bash

    usage: ecs-composex config [-h] -f DOCKERCOMPOSEXFILE [-d OUTPUTDIRECTORY]

    optional arguments:
      -h, --help            show this help message and exit
      -f DOCKERCOMPOSEXFILE, --docker-compose-file DOCKERCOMPOSEXFILE
                            Path to the Docker compose file
      -d OUTPUTDIRECTORY, --output-dir OUTPUTDIRECTORY
                            Output directory to write all the templates to.



AWS & Docker Resources support
==============================

AWS Services
------------

* `AWS ECS`_
* `AWS RDS`_
* `AWS DynamoDB`_
* `AWS DocumentDB`_
* `AWS S3`_
* `AWS SQS`_
* `AWS Kinesis`_
* `AWS SNS`_
* `AWS ELBv2`_
* `AWS ACM`_
* `AWS AppMesh`_
* `AWS IAM`_
* `AWS KMS`_
* `AWS VPC`_
* `AWS EC2`_


docker-compose
--------------

* healthcheck
* environment
* secrets
* deploy/replicas: Define how many tasks you want running for your service.
* deploy/resources: Automatically map your services resources to an AWS Fargate compatible CPU/RAM combination
* image (that'd be a problem if that did not work!)

Why use ECS ComposeX ?
======================

ECS ComposeX (or ComposeX for friends) first came out in early March, with some very basic features
and has grown over the past few months to add more and more features.

Since then, AWS released Copilot and has announced working with Docker to implement similar capabilities to allow
developers to have a better experience at developing as they would normally do and deploying to ECS.

However, I found that the feature set still remains somewhat limited, and as a Cloud Engineer working daily with developers,
I constantly have to balance features for developers and best practice in using AWS.

And at this point in time, neither of the previous tools are mentioned allow to do what ECS ComposeX do:

* Retain full docker-compose format specification compatibility without introducing
  a new format (Copilot has its own Environment file format)
* Provide support for more AWS services, such as RDS, DynamoDB, SQS etc.,
  which is not something supported in the Docker ecs-plugin or desktop app.


Trying to implement DevOps starting with developers
----------------------------------------------------

Whilst this is something that can be used by AWS Cloud Engineers tomorrow to deploy applications on ECS on the behalf
of their developers, the purpose of ECS ComposeX is to enable developers with a simplistic and familiar syntax that
takes away the need to be an AWS Expert. If tomorrow developers using ComposeX feel comfortable to deploy services
by themselves, I would be able to stop hand-holding them all the time and focus on other areas.


Philosphy
==========

CloudFormation is awesome, the documentation is excellent and the format easy. So ECS ComposeX wants to keep the format
of resources Properties as close to the orignal as possible as well as making it easier as well, just alike resources
like **AWS::Serverless::Function** which will create all the resources around your Lambda Function as well as the function.

Community focused
------------------

Any new Feature Request submitted by someone other than myself will get their request prioritized to try address their
use-cases as quickly as possible.

`Submit your Feature Request here <https://github.com/lambda-my-aws/ecs_composex/issues/new/choose>`_

Ensure things work
------------------

It takes an insane amount of time to test everything as, generating CFN templates is easy, testing that everything
works end-to-end is a completely different thing.

I will always do my best to ensure that any new feature is tested end-to-end, but shall anything slip through the cracks,
please feel free to report your errors `here <https://github.com/lambda-my-aws/ecs_composex/issues/new/choose>`_


Modularity or "Plug & Play"
---------------------------

The majority of people who are going to use ECS ComposeX on a daily basis should be developers who need to have an
environment of their own and want to quickly iterate over it. However, it is certainly something that Cloud Engineers
in charge of the AWS accounts etc. would want to use to make their own lives easy too.

In many areas, you as the end-user of ComposeX will already have infrastructure in place: VPC, DBs and what not.
So as much as possible, you will be able in ComposeX to define `Lookup`_ sections which will find your existing resources,
and map these to the services.

Fargate First
-------------

However the original deployments and work on this project was done using EC2 instances (using SpotFleet), everything
is now implemented to work on AWS Fargate First (2020-06-06).

Documentation
=============

`Find all the documentation to get started and all the features references here. <https://docs.ecs-composex.lambda-my-aws.io>`_

.. tip::

    `Nightly documentation <https://nightly.docs.ecs-composex.lambda-my-aws.io/>`_ following the master branch.


RoadMap
========

* `Feature requests <https://github.com/lambda-my-aws/ecs_composex/projects/2>`_
* `Issues <https://github.com/lambda-my-aws/ecs_composex/projects/3>`_


Blog
====

Follow the news and technical articles on using ECS ComposeX on the `Blog`_

* `CICD Pipeline for multiple services on AWS ECS with ECS ComposeX`_


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

.. _AWS ECS: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/ecs.html
.. _AWS VPC: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/vpc.html
.. _AWS RDS: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/rds.html
.. _AWS DynamoDB: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/dynamodb.html
.. _AWS DocumentDB: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/docdb.html
.. _AWS ACM: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/acm.html
.. _AWS ELBv2: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/elbv2.html
.. _AWS S3: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/s3.html
.. _AWS IAM: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/ecs.details/iam.html
.. _AWS Kinesis: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/kinesis.html
.. _AWS SQS: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/sqs.html
.. _AWS SNS: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/sns.html
.. _AWS KMS: https://docs.ecs-composex.lambda-my-aws.io/syntax/composex/kms.html

.. _AWS EC2: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#ec2-resources-for-ecs-cluster
.. _AWS AppMesh: https://nightly.docs.ecs-composex.lambda-my-aws.io/readme/appmesh.html

.. _Lookup: https://nightly.docs.ecs-composex.lambda-my-aws.io/syntax/composex/common.html#lookup

.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoidThwNXVIKzVvSnlXcUNVRzVlNE5wN0FiWE4rYzYvaHRNMEM0ZHMxeXRLMytSanhsckozVEN3L1Y5Szl5ZEdJVGxXVElyalZmaFVzR2tSbDBHeFI5cHBRPSIsIml2UGFyYW1ldGVyU3BlYyI6IlZkaml2d28wSGR1YU1xb2ciLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=master

.. |DOCS_BUILD| image:: https://readthedocs.org/projects/ecs-composex/badge/?version=latest
        :target: https://ecs-composex.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. |PYPI_VERSION| image:: https://img.shields.io/pypi/v/ecs_composex.svg
        :target: https://pypi.python.org/pypi/ecs_composex

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

.. |QUALITY| image:: https://sonarcloud.io/api/project_badges/measure?project=lambda-my-aws_ecs_composex&metric=alert_status
    :alt: Code scan with SonarCloud
    :target: https://sonarcloud.io/dashboard?id=lambda-my-aws_ecs_composex
