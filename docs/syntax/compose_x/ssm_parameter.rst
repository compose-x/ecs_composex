
.. meta::
    :description: ECS Compose-X AWS DynamoDB syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS SSM, SSM Parameter

.. _ssm_parameter_syntax_reference:

=================
x-ssm_parameter
=================


.. code-block:: yaml
    :caption: Syntax reference

    x-ssm_paramter:
      parameter-name:
        Properties: {}
        MacroParameters: {}
        Settings: {}
        Services: {}
        Lookup: {}

Create new SSM Parameters, including from local files with optional transformations.

Services
========

.. code-block:: yaml
    :caption: Define services

    Services:
      serviceA:
        Access: RW
      serviceB:
        Access: RO

IAM Permissions
----------------

ECS Compose-X defined access names:

* RW : Allow read/write to the parameter including by path
* RWStrict: Similarly to RW, without ByPath support
* RO: Allow read only to the parameter including by path
* ROStrict: Similarly to RO, without ByPath support


Properties
===========

Refer to `AWS CFN SSM Parameter Documentation`_. We support all of the definition and test with the documentation examples.

.. literalinclude:: ../../../use-cases/ssm/simple_parameter.yml
    :language: yaml
    :caption: Simple examples for x-ssm_parameter

MacroParameters
================

.. code-block:: yaml

    MacroParameters:
        FromFile: path/to/file/from/command_exec
        ValidateJson: true|false
        MinimizeJson: true|false
        IgnoreInvalidJson: true|false
        ValidateYaml: true|false
        IgnoreInvalidYaml: true|false
        RenderToJson: true|false

FromFile
--------

Path to file that you want to read the content of as the value for the SSM Parameter.

.. warning::

    Do not use binary type content, only text should be used

ValidateJson
--------------

If the input is a file and you expect it to be a valid JSON, this will validate whether the value is correct.
Fails the execution if is not

IgnoreInvalidJson
--------------------

Allows to ignore the JSON validation errors

MinimizeJson
-------------

If your input is nicely indented etc, this allows to compact it into a minimize JSON

ValidateYaml
-------------

When using a file, allows to ensure that the structure and content is a valid YAML

IgnoreInvalidYaml
-----------------

Allows to ignore the YAML validation errors

RenderToJson
---------------

This allows to render a content written in YAML for human friendly-ness, into a minimized JSON

.. warning::

    This will require that the input is valid YAML and will ignore if not.

Settings
========

See the :ref:`settings_syntax_reference` for more details.

.. hint::

    Given AWS SSM Parameter is serverless, there is no **Subnets** override.


Lookup
======

For more details, see the :ref:`lookup_syntax_reference`.

.. code-block:: yaml
    :caption: Lookup DynamoDB Table example

    x-ssm_parameter:
      parameterA:
        Lookup:
          Tags:
            - owner: myself
            - costallocation: 123
        Services:
          - name: serviceA
            access: SSMParameterReadPolicy

JSON Schema
============

Model
-------

.. jsonschema:: ../../../ecs_composex/ssm_parameter/x-ssm_parameter.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/ssm_parameter/x-ssm_parameter.spec.json


Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/ssm>`__ to use
as reference for your use-case.


.. _AWS CFN SSM Parameter Documentation: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ssm-parameter.html
.. _SSMParameterReadPolicy: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-template-list.html#ssm-parameter-read-policy
