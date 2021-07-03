.. meta::
    :description: ECS Compose-X AWS CodeGuru syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CodeGuru, APM, profiling

.. _codeguru_profiler_syntax_reference:

==============================
x-codeguru_profiler
==============================

.. contents::
    :depth: 2


Syntax
=======

.. code-block:: yaml

    Properties: {}
    MacroParameters: {}
    Lookup: {}
    Services: []

.. hint::

    Using ECS ComposeX, this automatically adds an Environment variable to your container,
    and **AWS_CODEGURU_PROFILER_GROUP_NAME** of the newly created Profiling Group.

.. hint::

    If you do not specify any Properties, the Profiling group name gets generated for you.

.. tip::

    You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/codeguru>`__ to use
    as reference for your use-case.

Properties
===========

Ths properties allow to use the same definition as in AWS Syntax Reference.

.. seealso::

    `AWS CFN definition for CodeGuru profiling group <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-codeguruprofiler-profilinggroup.html>`__

MacroParameters
================

AppendStackId
--------------

Type: Boolean
Description: Allows you to automatically add the stack ID to the provided Profiling Group Name so you can have multiple
profiling groups of the same logical name in your compose definition but different names when deploying to the same account
and same AWS region.

.. tip::

    We recommend to set the value to True at all times, but did not make it default.

Lookup
========

See :ref:`lookup_syntax_reference` for syntax.

.. note::

    For Lookup as when you create it, the profiling group name is available via **AWS_CODEGURU_PROFILER_GROUP_NAME**
    environment variable.

Example
=======

.. code-block:: yaml

    x-codeguru_profiler:
        Profiler01:
          Properties: {}
        Services:
            - name: service01
              access: RW

.. attention::

    The only valid access mode is **RW**

Code Example
-------------

Full Applications code used for this sort of testing can be found `here <https://github.com/lambda-my-aws/composex-testing-apps/tree/main/app02>`__
