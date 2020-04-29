ecs_composex.rds
===========================

This package is here to create all the CFN templates necessary to create RDS instances and allow microservices
to access the databases.

.. contents::

Assumptions
-----------

RDS is far more complex to configure and allow access to from microservices than pure IAM (at least at this time, using
IAM based auth might have performances impact on your applications, so we are going to consider usual DB credentials
are in use).

The engine
-----------

The engine & engine version are going to be used to determine if you are trying to create an Aurora Cluster in RDS
or a normal traditional DB. You have nothing more to do.

Security groups configuration
------------------------------

Per database, is created one Security Group for the DB itself and another that will be assigned to all microservices
which have been registered to have access to the database. However, keep in mind the `SG Account limitations`_ which apply,
by default, 5 Security Groups max per ENI. Given we are in *awsvpc* networking mode, each microservice running (container)
has its own ENI.


Credentials
-----------

AWS Secrets Manager integrates very nicely to AWS RDS. This has no intention to implement the rotation system at this
point in time, however, it will generate the password for the database and expose it securely to the microservices which
can via environment variables fetch

* DB Endpoint
* DB username
* DB Password
* DB Port

.. _`SG Account limitations`: https://aws.amazon.com/premiumsupport/knowledge-center/increase-security-group-rule-limit/


Standalone usage
----------------

You can use ECS ComposeX to create a standalone version of your RDS database.
