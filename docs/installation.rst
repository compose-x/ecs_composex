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

    $ git clone git://github.com/lambda-my-aws/ecs_composex

Or download the `tarball`_:

.. code-block:: console

    $ curl -OJL https://github.com/lambda-my-aws/ecs_composex/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/lambda-my-aws/ecs_composex
.. _tarball: https://github.com/lambda-my-aws/ecs_composex/tarball/master
.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/
