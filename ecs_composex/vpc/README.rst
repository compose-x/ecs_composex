ecs_composex.vpc
================

I am not here to tell you what a VPC should look like. So in that spirit, this is really here to be one
less thing developers who wish to use that tool are going to have to think about.

Outputs and exports
--------------------

By default, all outputs are also exported, and for the VPC it is a particularly useful one.
If you want to create resources which are today not supported by ECS ComposeX but with to use CFN
or something else like Terraform to identify and get subnet IDs, CIDR and otherwise, you will get these
from CFN exports.


Using an existing VPC
---------------------

You might already have network configuration and VPC setup all done, and want to simply plug-and-play to that existing
network configuration you have.

To help with that, we have added the **x-vpc** key support in the docker-compose file, with allows you to find your VPC
in and subnets with many options. Head to :ref:`vpc_syntax_reference` to see how to use that feature.


.. _vpc_network_design:

Default VPC Network design
--------------------------

The design of the VPC generated is very simple 3-tiers:

* Public subnets, 1/4 of the available IPs of the VPC CIDR Range
* Storage subnets, 1/4 of the available IPs of the VPC CIDR Range
* Application subnets, 1/2 of the available IPs of the VPC CIDR Range

I used to have a calculator for CIDR Range that would do things in percentage so it would be far more
granular but I found that it wasn't worth going so in depth into it.

Network architects out there will have created the VPCs by other means already or already know exactly what
and how they want these configured.

If that is not the case and you just want a VPC which will work with ingress and egress done in a
sensible way, use the *--create-vpc* argument of the CLI.

Default range
-------------

The default CIDR range for the VPC is **100.127.254.0/24**. It can be overridden with *--vpc-cidr*

This leaves a little less than 120 IP address for the EC2 hosts and/or Docker containers.

RoadMap
-------

* Add option to enable VPC Flow logs
* Add option to enable VPC Endpoints
