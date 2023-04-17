

.. _wafv2_webacl_syntax:

=====================================
x-wafv2_webacl - AWS::WAFv2::WebACL
=====================================

Module to create/use existing ``AWS::WAFv2::WebACL``

.. code-block:: yaml

    x-wafv2_webacl:
      managed-wafv2_webacl-01:
        Properties: {}
        Lookup:
          Arn: <>
          Identifier: <>

Properties
===========

Refer to the `WAFv2 WebACL properties`_

Lookup
=======

Lookup for WAFv2 WebACL is different: **you cannot use Tags**
Instead you must set one of

* ``Arn`` : The ARN of the WebACL
* ``Identifier``: The Identifier of the WebACL in the format ``name|id|scope``

Other parameters for Lookup (RoleArn etc.) are valid as for other resources.

Services
=============

There is no association at the moment with services as the WAF is considered an "Environment" resource, not one to be
interacted with by ECS services.

If you need this feature, please open a Feature Request.


ReturnValues
---------------

You can export to environment variables the native `AWS WAFv2 WebACL.ReturnValues`_, as per the documentation.

.. hint::

    The only one excluded is Capacity as it is a number. Open a new FR to retrieve it.


JSON Schema
============

Model
-------

.. jsonschema:: ../../../ecs_composex/wafv2_webacl/x-wafv2_webacl.spec.json

Definition
-----------

.. literalinclude:: ../../../ecs_composex/wafv2_webacl/x-wafv2_webacl.spec.json


Test files
============

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/wafv2_webacl>`__ to use
as reference for your use-case.


.. meta::
    :description: ECS Compose-X AWS WAFv2 WebACL
    :keywords: AWS, ecs,  waf, security

.. _AWS WAFv2 WebACL.ReturnValues: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-wafv2-webacl.html#aws-resource-wafv2-webacl-return-values
.. _WAFv2 WebACL properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-wafv2-webacl.html#aws-resource-wafv2-webacl-properties
