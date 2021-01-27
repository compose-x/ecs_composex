.. meta::
    :description: ECS Compose-X AWS CodeGuru syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS CodeGuru, APM, profiling

.. _codeguru_profiler_syntax_reference:

======================
x-codeguru-profiler
======================

Enables to use or create an existing/a new CodeProfiling group for your service.

Unlike most of the resources attachments, this is not done at the "family" level but at the service
level, as it might not be wanted to profile every single container in the task.

x-codeguru-profiler is a service/task level setting which offers a 1:1 mapping between your application
and the profiler.

.. hint::

    Using ECS ComposeX, this automatically adds an Environment variable to your container,
    **AWS_CODEGURU_PROFILER_GROUP_ARN** and **AWS_CODEGURU_PROFILER_GROUP_NAME** with the ARN
    of the newly created Profiling Group.

Syntax reference / Examples
==============================

I wanted to make it easy for people to use as well as being flexible and support all CFN definition.


.. code-block:: yaml
    :caption: Syntax for setting pre-defined codeprifiling group without creating a new one.

    x-codeguru-profiler: name (str)


.. code-block:: yaml
    :caption: Create a new CodeProfiling group with default settings.

    x-codeguru-profiler: True|False (bool)

.. code-block:: yaml
    :caption: Properties as defined in AWS CFN for ProflingGroup

    x-codeguru-profiler:
      AgentPermissions: Json
      AnomalyDetectionNotificationConfiguration:
        - Channel
      ComputePlatform: String
      ProfilingGroupName: String
      Tags:
        - Tag


.. seealso::

    `AWS CFN definition for CodeGuru profiling group <https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-codeguruprofiler-profilinggroup.html>`__

.. note::

    When you define the properties, in case you already had principals, it will still automatically
    add the **IAM Task Role** to the list of Principals that should publish to the profiling group.

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
