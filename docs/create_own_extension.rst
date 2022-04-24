
.. meta::
    :description: ECS Compose-X extensions
    :keywords: AWS, AWS ECS, Docker, docker-compose, CDK

.. _create_own_extension:

==========================
Create your own extension
==========================

Since 0.18, a mod manager has been implemented to allow other developers to create their own extensions.

The idea is simple: as an engineer you want to provide your developers with new features to create further
resources, linked (or not) to ECS Services. You want to maintain a well known format, using AWS CloudFormation and
docker-compose.

Given that ECS Compose-X will handle loading all the configuration files, the services, etc, all you now have to do
is create your own module, implement a few entrypoint functions to invoke, and that's it.

Why would one create their own extension?
============================================

Up until this new version, every new module would be added into the main package. And you are absolutely welcome
to contribute directly to this repository. But what if you needed something done faster? Or private ? Or to change
a core behaviour that you would otherwise disagree on with what's done today?

Creating your own extension is not only to add more AWS Resources, it can do anything you want, in the way you want it
to be, and include exotic resources that you might have privately published to AWS CloudFormation registry.

Generally speaking, any AWS resource you would like to see implemented/supported in ECS Compose-X, feel free to open
a new `Feature Request.`_

Using Cookiecutter
=====================

Cookiecutter is a very well-know project used by many others, sometimes without you even noticing, such as AWS SAM CLI.
Head to the `Cookiecutter GH repository`_  and `Cookiecutter documentation page`_ for more details.

The ECS Compose-X cookiecutter will create the required layout for the new module, which you are then free to change
and to adapt in order to achieve your goal.


.. code-block:: bash

    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install pip -U
    pip install cookiecutter
    # Use the cookiecutter, option 1
    cookiecutter gh:compose-x/cookiecutter-ecs_composex_extension

    # Option 2
    #git clone https://github.com/compose-x/cookiecutter-ecs_composex_extension.git
    #cookiecutter cookiecutter-ecs_composex_extension

Required entrypoints
=======================

.. note::

    For the rest of this documentation, we are going to assume that the extension name is ``x-msk_topic``.

First of all, your package must be called ``ecs_composex_<extension>`` in order to be imported, so here with our example,
``ecs_composex_msk_topic``


For the module to be detected and validated for import by ECS Compose-X "core", you need to have in your python
package, a few files, based on the name of your extension.

Must have
----------

* {{ extension }}_stack.py - Will have a Class called ``XStack`` which is a Subclass from ``ecs_composex.common.stacks.ComposeXStack``

In the same module or into a different one, you must define your resource, as a subclass of ``ecs_composex.compose.x_resources.XResource``
For example

.. code-block:: python

    from ecs_composex.compose.x_resources.services_resource import ServiceResource


    class MskTopic(ServiceResource):
        """Implement the resource class"""

When using the cookiecutter, both these endpoints will be generated for you to make it easier to get started, but
feel free to change these in which ever way you want.

Should have
-------------

* {{ extension }}.spec.json - JSON Specification format that will allow to validate user inputs.

Nice to have
--------------

We highly recommend to have the following modules in your py-package as per the cookiecutter.

* {{ extension }}_params.py - To have any CFN Parameters that you might want to use as properties. Use ``ecs_composex.common.cfn_params.Parameter``
* {{ extension }}_template.py - Module that would implement the logic of creating a new stack with new resources and define their template.


Testing the extension
======================

Along with creating a baseline of source code for you, the cookiecutter will also create a suite of tests files

* ``use-cases/*`` will have compose files where you can define your resources, properties, lookup etc, which are great to use as examples.
* ``features/*`` is here to allow `behave`_ to automatically get tests started to asses that the module is working
* ``tests/`` is here for you to write any static tests using `pytest`_

Licensing the extension
========================

By default, the cookiecutter licenses the work using Mozilla Public License 2.0 (MPL-2.0), as the main project is,
but you are totally free to license your work/extension with a license of your choosing.
Public extensions and contributions much appreciated.

Because the extension is, an extension, it is not part of ECS Compose-X "the work" and therefore gives you total freedom
to adopt another license. If you want to create private packages/extensions, you can do that too.


.. _Cookiecutter GH repository: https://github.com/cookiecutter/cookiecutter
.. _Cookiecutter documentation page: https://cookiecutter.readthedocs.io/en/1.7.2/
.. _behave: https://behave.readthedocs.io/en/stable/
.. _pytest: https://docs.pytest.org/en/7.1.x/
.. _Feature Request.: https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=enhancement&template=feature_request.md&title=%5BFR%5D+%3Caws+service%7Cdocker+compose%3E+
