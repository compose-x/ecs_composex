ecs_composex.appmesh
====================

AWS AppMesh is a service mesh which takes care of routing your services packets logically among the different nodes.
What this allows you to do, it to explicitly declare which services have access to others, either on http, tcp or gRPC.

.. note::

    For HTTP, it supports both http2 and http.

There are a lot more features to know about, so I would recommend to head to the `AWS Appmesh official documentation`_.

.. warning::

    At the time of working on this feature, mutualTLS is not available, for lack of $$ to use AWS ACM CA and do the dev
    work.

.. warning::

    By default in ECS Compsoex, the EGRESS policy for nodes it to DROP_ALL so that only explicitly allowed traffic can
    go across the mesh, in/out the services.

Nodes
-----

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
-------

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
