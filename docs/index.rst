
.. meta::
    :description: ECS Compose-X - README
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose

========================================
Welcome to ECS Compose-X documentation
========================================

|PYPI_VERSION| |PYPI_LICENSE| |PY_DLS|

|CODE_STYLE| |TDD| |BDD|

|QUALITY| |BUILD|

---------------------------------------------------------------------------------------------------------------
Manage, Configure and deploy your applications/services and AWS resources from your docker-compose definitions
---------------------------------------------------------------------------------------------------------------

What does it do?
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

Via pip
--------

.. code-block:: bash

    pip install ecs_composex


Using docker
--------------

.. code-block:: bash

    docker run --rm -v ~/.aws:/root/.aws public.ecr.aws/compose-x/compose-x:latest


How is it different ?
=====================

There are a lot of similar tools out there, including published by AWS. So here are a few of the features
that we think could be of interest to you.

Works with docker-compose
--------------------------

The most important thing for ECS Compose-X is to allow people to use the same compose files they use locally to spin
services up in AWS ECS. Other tools, such as Copilot, require you to rewrite into their specific format and input.

Modularity and "Plug & Play"
-----------------------------

ECS Compose-X on was written to make AWS accessible to developers and cloud engineers of all level.
For developers, we hope that enables them to create new environment of their own and want to quickly iterate over it.

In many areas, the end-user of Compose-X will already have infrastructure in place: VPC, Databases in AWS RDS, DynamoDB tables, etc.
With Compose-X you can define :ref:`lookup_syntax_reference` sections which will find your existing resources,
and map these to the new services.

.. note::

    When using :ref:`lookup_syntax_reference`, the resource in AWS will **never** be altered to avoid conflicts.


Easy compute definition
------------------------

ECS Compose-X allows you to define which services should be running on EC2 / Fargate, use ARM64 or X86_64 architecture,
CapacityProviders etc. for each individual service.

When using :ref:`lookup_syntax_reference`, it will also automatically detect configuration, which avoids configuration
settings conflicts and errors.

Supports AWS ECS Anywhere
--------------------------------

For enterprises, as much as for enthusiasts home-labbers out there, ECS Anywhere allows us to manage our services
definitions and deployment using AWS ECS as the control plane, and on-premise hardware or VMs to run the linux containers.

Adding since 0.18, you can now get ECS Compose-X to generate all the resources and configuration necessary to provision
your infrastructure (in AWS) and services.

.. seealso::

    See how to enable ECS Anywhere with :ref:`ecs_anywhere_compute_platform`

Attributes auto-correct
-------------------------

A fair amount of the time, deployments via AWS CloudFormation, Ansible and other IaC will fail because of incompatible
settings. This happened a number of times, with a lot of different AWS Services.

Whilst giving you the ability to use all properties of AWS CloudFormation objects, whenever possible, ECS Compose-X
will understand how two services are connected and will auto-correct the settings for you.

For example, if you set the Log retention to be 42 days, which is invalid, it will automatically change that to the
closest valid value (here, 30).

Using JSON Schema specifications
---------------------------------

Docker Compose follows a well known, well documented and open source JSON Schema definition to ensure consistency in the
compose files syntax, making it very accessible for all to use.

ECS Compose-X uses that schema definition to ensure compatibility with ``docker-compose``, and uses JSON Schemas
for extensions in order to ensure the compose files input are correct before doing any further processing.


.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiWjIrbSsvdC9jZzVDZ3N5dVNiMlJCOUZ4M0FQNFZQeXRtVmtQbWIybUZ1ZmV4NVJEdG9yZURXMk5SVVFYUjEwYXpxUWV1Y0ZaOEcwWS80M0pBSkVYQjg0PSIsIml2UGFyYW1ldGVyU3BlYyI6Ik1rT0NaR05yZHpTMklCT0MiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main

.. |DOCS_BUILD| image:: https://readthedocs.org/projects/ecs-composex/badge/?version=latest
        :target: https://ecs-composex.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

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


.. toctree::
    :maxdepth: 1
    :caption: Getting Started

    requisites
    installation
    lexicon
    contributing

.. include:: examples.rst
.. include:: compatibility_matrix.rst
.. include:: modules_syntax.rst


.. toctree::
    :titlesonly:
    :caption: Additional content

    changelog
    extras
    story

.. toctree::
    :titlesonly:
    :maxdepth: 1
    :caption: Library Modules

    modules

Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. meta::
    :description: ECS Compose-X
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose


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
.. _ECS Compose-X: https://github.com/compose-x/ecs_composex
.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
.. _ECS Compose-X Project: https://github.com/orgs/lambda-my-aws/projects/3
.. _CICD Pipeline for multiple services on AWS ECS with ECS Compose-X: https://blog.ecs-composex.lambda-my-aws.io/posts/cicd-pipeline-for-multiple-services-on-aws-ecs-with-ecs-composex/
.. _the compatibilty matrix: https://nightly.docs.compose-x.io/compatibility/docker_compose.html
.. _Find out how to use ECS Compose-X in AWS here: https://blog.compose-x.io/posts/use-your-docker-compose-files-as-a-cloudformation-template/index.html
