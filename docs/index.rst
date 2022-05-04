
.. meta::
    :description: ECS Compose-X - README
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose

##########################################
Welcome to ECS Compose-X documentation
##########################################

|PYPI_VERSION| |PYPI_LICENSE| |PY_DLS|

|CODE_STYLE| |TDD| |BDD|

|QUALITY| |BUILD|

-----------------------------------------------
The no-code CDK for docker-compose & AWS ECS
-----------------------------------------------

**Deploy your services to AWS ECS from your docker-compose files in 3 steps**

* Step 1. Install ECS Compose-x
* Step 2. Use your existing docker-compose files. Optionally, add Compose-X extensions.
* Step 3. Deploy to AWS via CloudFormation.
* Step 4 ? Repeat.


What does it do?
========================

* Simplify applications and resources deployment to AWS for developers/SRE/Cloud engineers
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


Install
============

.. code-block:: bash

    # Inside a python virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install ecs-composex

    # For your user only, without virtualenv
    pip install ecs-composex --user


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

The origin of ECS Compose-X was to provide developers with the ability of deploying an entire test stack from scratch.
However, the reality is more that companies have already gotten VPC/Networking sorted out, other applications, services
and resources already exist and new services need access to that existing infrastructure.

So with ECS-ComposeX we have since very early on , defined :ref:`lookup_syntax_reference`, which allows you to use your existing services
and resources you have in AWS. Via API discovery, all the settings, configuration of those will be used to grant
the necessary access and define configuration accordingly for your services to use these successfully.

ECS Compose-X on was written to make AWS accessible to developers and cloud engineers of all level.
For developers, we hope that enables them to create new environment of their own and want to quickly iterate over it.

.. note::

    When using :ref:`lookup_syntax_reference`, the resource in AWS will **never** be altered to avoid conflicts.


Deploy to AWS Fargate, AWS EC2 and ECS Anywhere
---------------------------------------------------

Since the beginning, the focus has been on running with AWS Fargate, as it is what allows developers least effort
to deploying applications. But by users demand, the project was adapted to support deploying to existing EC2 based
clusters, as well as on ECS Anywhere.

With the growing adoption of other ARM there is also now support to specify whether you want to run your services
on AWS Fargate using Graviton processors.


.. seealso::

    See how to enable ECS Anywhere with :ref:`ecs_anywhere_compute_platform`

Easy compute definition
------------------------

ECS Compose-X allows you to define which services should be running on EC2 / Fargate, use ARM64 or X86_64 architecture,
CapacityProviders etc. for each individual service.

When using :ref:`lookup_syntax_reference`, it will also automatically detect configuration, which avoids configuration
settings conflicts and errors.

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

    requisites
    installation
    lexicon
    syntax/compose_x/common
    compatibility_matrix

.. toctree::
    :maxdepth: 1
    :caption: Examples and Help

    examples
    how_tos
    extras

.. toctree::
    :maxdepth: 1
    :caption: Additional extensions

    create_own_extension
    community_extensions


.. include:: modules_syntax.rst


.. toctree::
    :titlesonly:
    :caption: Additional content

    changelog
    story

.. toctree::
    :titlesonly:
    :maxdepth: 1
    :caption: Modules and Source Code

    modules
    contributing

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
