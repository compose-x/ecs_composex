.. meta::
    :description: ECS Compose-X AWS CodeGuru syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CodeGuru, APM, profiling

.. _codeguru_profiler_syntax_reference:

==============================
x-codeguru_profiler
==============================

Enables to use or create a new AWS Code Guru profiling group.

.. code-block:: yaml

    Properties: {}
    MacroParameters: {}
    Services: []

.. hint::

    Using ECS ComposeX, this automatically adds an Environment variable to your container,
    **AWS_CODEGURU_PROFILER_GROUP_ARN** and **AWS_CODEGURU_PROFILER_GROUP_NAME** with the ARN
    of the newly created Profiling Group.

.. hint::

    If you do not specify any Properties, the Profiling group name gets generated for you.

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

Example
--------

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
=============

Here is an example of a simple Flask application I added the codeguru profiler for.

.. code-block:: python

    import boto3
    import logging
    from aws_xray_sdk.ext.flask.middleware import XRayMiddleware
    from aws_xray_sdk.core import patcher, xray_recorder
    from werkzeug.middleware.proxy_fix import ProxyFix
    from codeguru_profiler_agent import Profiler
    from app02 import APP


    def start_app():
        debug = False
        if "DEBUG" in APP.config and APP.config["DEBUG"]:
            debug = True

        if "USE_XRAY" in APP.config and APP.config["USE_XRAY"]:
            xray_recorder.configure(service=APP.name)
            XRayMiddleware(APP, xray_recorder)
            xray_recorder.configure(service="app01")
            if "USE_XRAY" in APP.config and APP.config["USE_XRAY"]:
                patcher.patch(
                    (
                        "requests",
                        "boto3",
                    )
                )
            print("Using XRay")

        if APP.config["AWS_CODEGURU_PROFILER_GROUP_NAME"]:
            p = Profiler(
                profiling_group_name=APP.config["AWS_CODEGURU_PROFILER_GROUP_NAME"],
                aws_session=boto3.session.Session(),
            )
            p.start()
            print(
                f"Started profiler {p} for {APP.config['AWS_CODEGURU_PROFILER_GROUP_NAME']}"
            )
            logging.getLogger('codeguru_profiler_agent').setLevel(logging.INFO)

        APP.wsgi_app = ProxyFix(APP.wsgi_app)
        APP.run(host="0.0.0.0", debug=debug)


    if __name__ == "__main__":
        start_app()

.. seealso::

    Full Applications code used for this sort of testing can be found `here <https://github.com/lambda-my-aws/composex-testing-apps/tree/main/app02>`__
