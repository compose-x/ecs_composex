.. meta::
    :description: ECS Compose-X install
    :keywords: AWS, AWS ECS, Docker, Containers, Compose, docker-compose, install, setup

============
Installation
============

.. include:: macro_install.rst


Stable release
==============

From Pip
---------

To install ECS-Compose-X, run this command in your terminal:

.. code-block:: console

    $ pip install ecs_composex

This is the preferred method to install ECS-Compose-X, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guides
you through the process.


From sources
============

The sources for ECS-Compose-X can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/compose-x/ecs_composex

Or download the `tarball`_:

.. code-block:: console

    $ curl -OJL https://github.com/compose-x/ecs_composex/tarball/main

Once you have a copy of the source, you can install it

.. hint::

    Highly recommend to create a new python virtualenv in order not to spread on all your machine

    .. code-block:: console

        python -m venv venv
        source venv/bin/activate

Using pip
-----------

.. code-block:: console

    # After git clone
    cd ecs_composex
    pip install .

Using poetry
-------------------

.. code-block:: console

    # After git clone
    cd ecs_composex
    python -m pip install poetry
    poetry install

.. hint::

    Using poetry will also install all the dev dependencies for local dev.

.. _Github repo: https://github.com/compose-x/ecs_composex
.. _tarball: https://github.com/compose-x/ecs_composex/tarball/master
.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/
