Ingress Logic
==============

For TCP based access from microservices to resources such as RDS, EFS etc., we need to define security group ingress
accordingly.

There is a default limit of 60 rules per security group, therefore, when a database is global or needs access by a large
number of microservices, we need to change strategy. We also have a default limit of Security Groups per ENI, which by
default is 5. So we have to group as many services which have the same access pattern together in order to be within the
boundaries of the `VPC Limits`_.

.. hint::

    See `VPC Limits`_ for default VPC settings. These can be changed, but ECS ComposeX assumes you are using the default
    settings.


Case 1. x-resource has 40 or more services defined
---------------------------------------------------

First we are going to evaluate whether or not the service itself has more than 40 microservices listed.
If there are more than 40 services listed that require access, then we are going to create a new security group
which is going to be associated to the services and we will only have one rule to allow traffic from that new SG
to the SG of the resource.


Case 2. x-resource has less than 40 services defined
-----------------------------------------------------

Opposite case from above, in which case we simply generate a list of ingress rules that will be added to the resource
security group.


Case 3. x-resource has `is_global` setting true
------------------------------------------------

Some resources might be considered "global" to the microservices, meaning, all microservices should be allowed access to
the resource. This is not best practice but it effectively achieves the same as for use-case 1.

Only this time instead of adding another security group and passing it onto the


Exception to Case 1.
--------------------

As mentioned before, there is a default limit of 5 SGs per ENIs. The difficulty is to merge Case 1 to that exception.
The example for this would be

* service needs access to a DB which has 40+ services defined
* service needs access to another DB which also has 40+ services defined
* service needs access to EFS which also has 40+ services.
* service needs access to ElasticCache which also has 40+ services
* service needs access to any endpoint in the VPC controlled by security group and uses 40+ services.


Agreed that this is an extreme use-case, but it doesn't mean it is not impossible.


.. note::

    I arbitrarily chose 40 as this is 2/3 of the maximum default, giving room for more.



.. _VPC Limits: https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html
