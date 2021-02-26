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

As a developer, working locally is a crucial part of your day to day work, and docker-compose allows you to do
just that, for simple services as well as very complex structures.

Your prototype works, and you want to deploy to AWS. But what about IAM ? Networking ? Security ? Configuration ?

Using ECS Compose-X, you keep your docker-compose deifnitions as they are, add the AWS services you have chosen
as part of that definition, such as ELB, RDS/DynamodDB Databases etc, and the program will automatically
generate all the AWS CloudFormation templates required to deploy all your services.

It automatically takes care of network access requirements and IAM permissions, following best practices.


Installation
============

ECS Compose-X can be used as a CLI ran locally, in CICD pipelines, or as an AWS CloudFormation macro, allowing you
to use your Docker Compose files directly in CloudFormation!

On AWS using AWS CloudFormation Macro
--------------------------------------

.. list-table::
    :widths: 50 50
    :header-rows: 1

    * - Region
      - Lambda Layer based Macro
    * - us-east-1
      - |LAYER_US_EAST_1|
    * - eu-west-1
      - |LAYER_EU_WEST_1|


.. |LAYER_US_EAST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/layer-macro.yaml

.. |LAYER_EU_WEST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/layer-macro.yaml

Via pip
--------

.. code-block:: bash

    pip install ecs_composex


CLI Usage
==========

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


`Find out how to use ECS Compose-X in AWS here`_

AWS & Docker Resources support
==============================

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
* `AWS VPC`_
* `AWS EC2`_

docker-compose
---------------

The docker-compose compatibility is aimed to be 100%. However, some features won't be supported by AWS ECS, or by AWS Fargate.
To have an extensive list of support, refer to `the compatibilty matrix`_

Documentation
=============

`Find all the documentation to get started and all the features references here. <https://docs.ecs-composex.lambda-my-aws.io>`_

.. tip::

    `Nightly documentation <https://nightly.docs.ecs-composex.lambda-my-aws.io/>`_ following the main branch.

RoadMap
========

* `Feature requests <https://github.com/lambda-my-aws/ecs_composex/projects/2>`_
* `Issues <https://github.com/lambda-my-aws/ecs_composex/projects/3>`_

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
.. _AWS ElastiCache: https://docs.compose-x.io/syntax/composex/elasticache.html
.. _AWS EC2: https://nightly.docs.ecs-composex.lambda-my-aws.io/features.html#ec2-resources-for-ecs-cluster
.. _AWS AppMesh: https://nightly.docs.ecs-composex.lambda-my-aws.io/readme/appmesh.html

.. _Lookup: https://nightly.docs.ecs-composex.lambda-my-aws.io/syntax/composex/common.html#lookup
.. _the compatibilty matrix: https://nightly.docs.compose-x.io/compatibility/docker_compose.html
.. _Find out how to use ECS Compose-X in AWS here: https://blog.compose-x.io/posts/use-your-docker-compose-files-as-a-cloudformation-template/index.html

.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiWjIrbSsvdC9jZzVDZ3N5dVNiMlJCOUZ4M0FQNFZQeXRtVmtQbWIybUZ1ZmV4NVJEdG9yZURXMk5SVVFYUjEwYXpxUWV1Y0ZaOEcwWS80M0pBSkVYQjg0PSIsIml2UGFyYW1ldGVyU3BlYyI6Ik1rT0NaR05yZHpTMklCT0MiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main

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

.. |QUALITY| image:: https://sonarcloud.io/api/project_badges/measure?project=lambda-my-aws_ecs_composex&metric=alert_status
    :alt: Code scan with SonarCloud
    :target: https://sonarcloud.io/dashboard?id=lambda-my-aws_ecs_composex
