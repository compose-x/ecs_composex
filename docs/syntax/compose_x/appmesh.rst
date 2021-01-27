.. meta::
    :description: ECS Compose-X AWS AppMesh syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS AppMesh, service mesh, mesh

.. _appmesh_syntax_reference:

==========
x-appmesh
==========

.. contents::
    :local:

.. warning::

    This module is still under development and we would love to get any feedback on the syntax and how to make it easier.


Syntax
=======

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
==========

MeshName
----------

This is the name of the mesh. However, if you do not specify the *MeshOwner*, then the name is ignored and the root
stack name is used.

The MeshName is going to be used if you specify the MeshOwner, in case you are deploying into a Shared Mesh.

.. code-block::

    AllowedPattern: ^[a-zA-Z0-9+]+$

MeshOwner
----------

The MeshOwner as described above, doesn't need to be specified, if you are creating your Nodes, Routers and Services
(virtual ones) into a Mesh shared with you from another account.

.. code-block::

    AllowedPattern: [0-9]{12}

EgressPolicy
-------------

The mesh aims to allow services, nodes to communicate to each other only through the mesh. So by default, ECS ComposeX
sets the policy to `DROP_ALL`. Meaning, no traffic out of the nodes will be allowed if not to a defined VirtualService
in the mesh.

For troubleshooting and otherwise for your use-case, you might want to allow any traffic to get out of the node anyway.
If so, simply change the policy to `ALLOW_ALL`

.. code-block::

    AllowedValues: DROP_ALL, ALLOW_ALL

Settings
=========

The settings section is where we are going to define how our services defined in Docker compose are going to integrate
to the mesh.

nodes
------

Syntax
""""""

.. code-block:: yaml

    Name: str # <family name>
    Procotol str
    Backends:
      - <service_name> # Only services can be defined as backend

Examples
""""""""

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
-------

Definition
""""""""""

Routers as mentioned in the module description, are here to allow developers to define how packets should be routed
from one place to another.

For TCP ones, one can only really set timeout settings, in addition to TLS etc. However for Http, Http2 and gRPC it
allows you to define further more rules. The example below shows how a request to the router on path **/** it should
send requests with the POST method to app02, but requests with the GET method to app01.

Syntax
""""""

.. code-block:: yaml

    Name: str
    Listener
      Procotol str
      port: int
    Routes:
      Http:
        - <match>

match
""""""

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
+++++++

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
--------

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


AWS AppMesh & AWS Cloud Map for services mesh & discovery
=========================================================

AWS AppMesh is a service mesh which takes care of routing your services packets logically among the different nodes.
What this allows you to do, it to explicitly declare which services have access to others, either on http, tcp or gRPC.

.. seealso::

    ComposeX :ref:`appmesh_syntax_reference` syntax reference

.. note::

    For HTTP, it supports both http2 and http.

There are a lot more features to know about, so I would recommend to head to the `AWS Appmesh official documentation`_.

.. warning::

    At the time of working on this feature, mutualTLS is not available, for lack of $$ to use AWS ACM CA and do the dev
    work.

.. warning::

    By default in ECS ComposeX, the EGRESS policy for nodes it to DROP_ALL so that only explicitly allowed traffic can
    go across the mesh, in/out the services.

Nodes
=====

The nodes are a logical construct to indicate an endpoint. With ECS ComposeX, it will either be

* a service defined and deployed in ECS
* a database
* any DNS discoverable target.

When you enable AWS AppMesh in ECS ComposeX, it will automatically add all the necessary resources for your ECS task
to work correctly:

* envoy container
* update task definition with proxy configuration
* add IAM permissions for envoy to discover services and the mesh settings.

Routers
=======

Routers are logical endpoints that apply the logic you define into routes. For TCP routers, it mostly is about defining
TCP settings, such as timeouts.

For HTTP and gRPC however, it is far more advanced. You can define routes based on path, method etc.
I also can perform healthcheck for you, to evaluate the nodes health.
It effectively is a virtual ALB listener with a long set of rules.

.. note::

    From experimenting and testing however, you cannot mix routes protocols within the same router.

Services
---------

The virtual services are once again, a logical pointer to a resource. That resource will either be a Node or a Router.
But again, it is aimed to be a virtual pointer, therefore, **you do not need to call your virtual service with the same
name as one of the services defined in the compose services**.

What does that mean?

In essence, when you define a VirtualService as the backend of a virtual node, this means this node and its services
will be granted access to the nodes of the VirtualService itself. But, you might have called your services **clock**
and **watch**, and yet the virtual service will be called **time**.

Problem: when trying to connect to the endpoint **time**, your application won't be able to resolve **time**.
Solution: ECS ComposeX will create a virtual service in the same AWS CloudMap as where the ECS Services are registered,
and create a fake instance of it, for which the IPv4 address will be **169.254.255.254**
How does it work?: your microservice in ECS will try to resolve **time**. The DNS response will be an IP address, here,
**169.254.255.254**. Which obviously does not exist in a VPC (see `RFC 3927`_ for more details) but, it will allow your
application to establish the connection. The connection is intercepted by the envoy proxy container, which internally
figures out, where to connect and how. It will then take your package, and send it across to the destination, **to the
right IP address**. **Which is why resolving the IP in DNS is important, but the value of the record is not.**


The other things ECS ComposeX takes care of for you
---------------------------------------------------

In addition to configuring the ECS Task definition appropriately etc, ECS ComposeX also will take care of the security
groups opening between the Virtual Nodes, and to other backends.

Yes, a mesh with DROP_ALL will ensure that communication between nodes only happens if explicitly allowed, but this
does not mean we should not also keep the underlying network in check.

The security group inbound rule defined is from the source node to the target node(s), allowing all traffic *for now*
between the nodes.

.. note::

    For troubleshooting, you can use the ClusterWide Security Group which is attached to all containers deployed with
    ECS ComposeX, and allow all traffic within the security group to allow your ECS Services to communicate.


.. _AWS Appmesh official documentation: https://docs.aws.amazon.com/app-mesh/latest/userguide/what-is-app-mesh.html
.. _RFC 3927: https://tools.ietf.org/html/rfc3927
.. _HTTP Route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-Httproutematch.html
.. _TCP Route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-Httproutematch.html
.. _gRPC route: Https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-appmesh-route-grpcroutematch.html
