.. _appmesh_syntax_reference:

==========
x-appmesh
==========

.. toctree::
    :maxdepth: 2

.. warning::

    This module is still under development and we would love to get any feedback on the syntax and how to make it easier.


Syntax definition
------------------

.. code-block:: yaml

    x-appmesh:
      Properties:
        MeshName: str
        MeshOwner: str
        EgressPolicy: str
      Settings:
        Nodes:
          - <node>
        Routers:
          - <router>
        Services:
          - <service>



The properties for the mesh are very straight forward. Even though, the wish with ECS ComposeX is to keep the Properties
the same as the ones defined in CFN as much as possible, for AWS AppMesh, given the simplicity of the properties,
we are going with somewhat custom properties, mostly to allow for more features integration down the line.

.. warning::

    There is only one mesh that will be either created or used to deploy the services into.

.. code-block:: yaml

    x-appmesh:
      Properties: {}
      Settings: {}

Properties
----------

MeshName
^^^^^^^^

This is the name of the mesh. However, if you do not specify the *MeshOwner*, then the name is ignored and the root
stack name is used.

The MeshName is going to be used if you specify the MeshOwner, in case you are deploying into a Shared Mesh.

.. code-block::

    AllowedPattern: ^[a-zA-Z0-9+]+$

MeshOwner
^^^^^^^^^

The MeshOwner as described above, doesn't need to be specified, if you are creating your Nodes, Routers and Services
(virtual ones) into a Mesh shared with you from another account.

.. code-block::

    AllowedPattern: [0-9]{12}

EgressPolicy
^^^^^^^^^^^^

The mesh aims to allow services, nodes to communicate to each other only through the mesh. So by default, ECS ComposeX
sets the policy to `DROP_ALL`. Meaning, no traffic out of the nodes will be allowed if not to a defined VirtualService
in the mesh.

For troubleshooting and otherwise for your use-case, you might want to allow any traffic to get out of the node anyway.
If so, simply change the policy to `ALLOW_ALL`

.. code-block::

    AllowedValues: DROP_ALL, ALLOW_ALL

Settings
--------

The settings section is where we are going to define how our services defined in Docker compose are going to integrate
to the mesh.

nodes
^^^^^

Syntax
""""""

.. code-block:: yaml

    Name: str # <family name>
    Procotol str
    Backends:
      - <service_name> # Only services can be defined as backend

Example
"""""""

This section represents the nodes. The nodes listed here must be either a service as listed in docker-compose or a
family name.

.. code-block::

    Nodes:
      - Name: app01
        Procotol Http
      - Name: app02
        Procotol Tcp
        Backends:
          - service-abcd

routers
^^^^^^^

Definition
""""""""""

Routers as mentioned in the module description, are here to allow developers to define how packets should be routed
from one place to another.

For TCP ones, one can only really set timeout settings, in addition to TLS etc. However for Http, Http2 and gRPC it
allows you to define further more rules. The example below shows how a request to the router on path **/** it should
send requests with the POST method to app02, but requests with the GET method to app01.

Syntax
"""""""

.. code-block:: yaml

    Name: str
    Listener
      Procotol str
      port: int
    Routes:
      Http:
        - <match>

matches
""""""""

This is simplistic version of the AWS Route Match specifications : `HTTP Route`_, `TCP Route`_

Definition
++++++++++

The match allows to define how to route packets to backend nodes

Syntax
++++++

.. code-block:: yaml

    Match:
      Prefix: str
    Method: str
    Scheme:: str
    Nodes:
      - <node_name>

Example
""""""""

.. code-block:: yaml

    Routers:
      - Name: Httprouter
        Listener
          Procotol Http
          port: 8080
        Routes:
          Http:
            - Match:
                Prefix: /
              Method: GET
              Scheme:: Http
              Nodes:
                - app01
            - Match:
                Prefix: /
              Method: POST
              Nodes:
                - app02

services
^^^^^^^^

The VirtualServices are what acts as backends to nodes, and as receiver for nodes and routers.
The Virtual Services can use either a Node or a Router as the location to route the traffic to.

Syntax
""""""

.. code-block::

    Services:
      - Node: <node_name>
        Name: str
      - Router: <router_name>
        Name: str

.. code-block:: yaml

    Services:
      - Name: service-xyz
        Router: Httprouter
      - Name: service-xyz
        Node: app03

Examples
--------

.. literalinclude:: ../../../use-cases/appmesh/new_mesh.yml
    :language: yaml

.. _HTTP Route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-Httproutematch.html
.. _TCP Route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-Httproutematch.html
.. _gRPC route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-grpcroutematch.html
