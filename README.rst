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

-----------------------------------------------
The no-code CDK for docker-compose & AWS ECS
-----------------------------------------------

Deploy your services to AWS ECS from your docker-compose files in 3 steps

* Step 1. Install ECS Compose-x
* Step 2. Use your existing docker-compose files. Optionally, add Compose-X extensions.
* Step 3. Deploy to AWS via CloudFormation.


What does it do?
========================

* Help developers/SRE/Cloud engineers to deploy applications to AWS using docker-compose syntax
    * Generates CloudFormation templates out of the Compose Files
    * Links services and AWS Resources together via IAM / Networking / Configuration
    * Detects mis-configurations and autocorrects wherever possible

* Use/Re-use existing docker-compose files and compose specifications
    * Supports docker-compose specification 3.7+
    * Performs JSON validation of input to improve reliability
    * Enable/disable features to run in AWS Fargate automatically

* Expand the definitions with AWS CloudFormation resources
    * For supported resources, supports full CloudFormation properties
    * For existing resources, will detect them and allow to use the ``Return Values`` with other components

* Allows to use existing resources in your AWS Account
* Can be extended with custom modules/hooks


Useful Links
===============

* `Documentation`_
* `Labs <https://labs.compose-x.io/>`_
* `Feature requests`_
* `Issues`_
* `Compatibility Matrix`_


Installation
=====================

.. code-block:: bash

    # Inside a python virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install ecs-composex

    # For your user only
    pip install ecs-composex --user

Usage
======

.. code-block:: bash

    # Get all the options
    ecs-compose-x -h

    # Simple example using docker-compose file and an extension with your AWS Settings
    ecs-compose-x render -d templates -n my-new-stack -f docker-compose.yaml -f aws-settings.yaml


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
.. _Feature requests: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=enhancement&template=feature_request.md&title=%5BFR%5D+%3Caws+service%7Cdocker+compose%3E+
.. _Issues: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=bug&template=bug_report.md&title=%5BBUG%5D


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
