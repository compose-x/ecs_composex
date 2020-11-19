.. _aws_rds_readme:

=======
AWS RDS
=======

AWS RDS is one of the most amazing and feature rich service on AWS. Which also means that it is one of the possibly
most complex to get right. AWS has done an amazing job at making RDS easy to consume but still requires a lot of
settings to come together.

With AWS Aurora, and global databases etc, it becomes something that could be very complicated to describe in only a few
lines.

Our objective with this module is to make some of the most common usage of AWS RDS, with a push for RDS Aurora, easy
for developers and cloud engineers to define in a very simple way common RDS deployment patterns.

Defaults
===========

Credentials
-----------

Aurora and traditional RDS Databases support both Username/Password generic authentication. Due to the wide adoption of
that authentication mechanism, all RDS Dbs will come with a username/password, auto generated and stored in AWS Secrets Manager.


.. hint::

    We do plan to allow a tick button to enable Aurora authentication with IAM, however have not received a Feature Request
    for it.

AWS Secrets Manager integrates very nicely to AWS RDS. This has no intention to implement the rotation system at this
point in time, however, it will generate the password for the database and expose it securely to the microservices which
can via environment variables fetch

* DB Endpoint
* DB username
* DB Password
* DB Port

Simple Properties
==================

AWS Aurora and RDS Instances both can accept 20+ Properties, with complex syntax on both of these. The objective with
ComposeX is to keep things very simple. Therefore, in the attempt of making it easier, you can today simply define only
two properties to get yourself up and running

* Engine
* EngineVersion

Security groups configuration
=============================

Per database, is created one Security Group for the DB itself and another that will be assigned to all microservices
which have been registered to have access to the database. However, keep in mind the `SG Account limitations`_ which apply,
by default, 5 Security Groups max per ENI. Given we are in *awsvpc* networking mode, each microservice running (container)
has its own ENI.


.. _`SG Account limitations`: https://aws.amazon.com/premiumsupport/knowledge-center/increase-security-group-rule-limit/

.. note::

    See :ref:`rds_syntax_reference` to start deploying (or re-use!) your services and connect them to RDS.
