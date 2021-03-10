=======
History
=======

0.13.0 (2021-03-10)
===================

This new version comes with a good mix of fixes and new features supported.
In an effort of always improving docker-compose compatibility, a number of features have been added.
Volumes support is added for both local volumes (non-bind) and shared volumes (via EFS).
Alarm support added to allow creating arbitrary alarms and scaling policies on metrics for non Compose-X managed
resources.

New Features
-------------

* 33f7b45 x-alarms support (#425)
* e12d25a ECS DeploymentConfiguration support with Circuit breaker (#423)
* dad6d02 awslogs drivers options support (#422)
* b66876b Added lookup for SecurityGroups in Ingress (#401)
* c3c1565 x-efs (#395)
* df7d085 Added tmpfs support
* d19e60d Added sysctls support
* 8c4c30e Added working_dir support
* 71cb736 Added shm_size support
* a09d233 Added cap_add,cap_drop support
* 69bc348 Added support for Ulimits
* 3f380c7 docker-compose ECS local volumes support (#391)

Fixes
------
* 811f88d Fixing URLs
* cae1336 build can be either a string or dict
* f093931 Fixed self-ingress process (#417)
* ec3dbc4 Fixing VpcId.Use and x-dns when not set (#415)
* f0d6635 Fixing lookup resource output condition (#411)
* 6dbef07 Fixing s3 to ecs bug for lookup (#400)
* 7edc838 Renamed and fixed condition for registries (#392)
* 8876047 For PrivateNamespace in CloudMap, using ns-ID (#388)
* b7130ea Family name is as defined in compose files, and LB use that name instead of logical name (#386)

Improvements
-------------

* 765426b Updated docs
* 07c6db2 Using troposphere 2.6.4
* 7a31e63 Simpler regexp to group required, ping and optional healthcheck (#416)
* 4977767 x-elbv2 settings in macro parameters for LB Attributes (#410)
* 0ea035a Code Cleanup and Refactor (#409)
* 8059454 Moved x-s3 settings to MacroParameters and cleaned up old unused code (#407)
* 8773299 Healthcheck times translated from str to int (#406)
* 5a49890 When not public NLB, allows to override the LB Subnets to use (#402)
* 695624f Added compatibility matrix (#398)
* ec184fc Generic attributes output configuration (#396)
* 5f1cc0b Adding a message to inform that no port were defined but UseCloudmap (#387)



0.12.0 (2021-01-31)
===================

New features
------------

* dd9246c Allowing to define features by names and related resources (#376) John Preston
* 2d0ef6d Allow to define RoleArn for DNS Lookup (#377) John Preston
* d85fd90 Add an IAM Role to RDS for S3import feature (#373) John Preston

Fixes
-----

* b690d60 Fixing ingress parsing for Ingress (#382) John Preston
* 01c0582 Fix import value for subnets to Join for custom subnets (#381) John Preston
* 8f2b777 Passing the subnets as a string with !Join from mappings (#380) John Preston
* d72e9c1 Fixed events. Dumbed down the Fargate version John Preston
* 913d451 Fixing AppMesh
* 397c4cf Fixed ACM certificate mapping (#366) John Preston
* f09ad64 Fix S3 name generation, events subnet param (#357) (jacku7) Jack Saunders

Improvements
------------

* 95f76ab Updated lookup based to be more accurate (#378) John Preston
* 62b27f7 Documentation updates/fixes and macro install/usage guide (#372) John Preston
* 1e77c87 Working lookup of DNS zones. Relies on DNS Name only. John Preston
* 5a8b659 VPC and subnets now in mappings John Preston
* 913d451 Zones require name John Preston
* 54593eb ECS Cluster "pointer" as a variable of settings John Preston
* d801463 * Files pulled for remote files are stored with tempfile * Fixing x-dns John Preston
* 0267cbc Refactor of DNS into more gracious handling John Preston
* e56b667 * Refactored ECS Cluster creation for simplicity John Preston
* ba511dd Create a nightly manifest list pointing always to the latest (#364) John Preston
* 3596286 Docker image release-work (#363) John Preston
* 02591ce Support for OIDC and Cognito AUTH action in x-elbv2 (#339) John Preston
* fb36420 Updating build conditions and methods (#362) John Preston
* 06d5776 Adding sitemap and meta keywords (#360) John Preston
* 29e75ef Re-arranging test files and patching up CI files (#361) John Preston

Special changes
---------------

The following changes all relate to the release a CFN Macro of ECS Compose-X

* 1aea413 Allow to set override Function IAM Role John Preston
* b804360 Maintain policy on previous layer versions (#383) John Preston
* 5fe8169 Adding retain policy on layer version permissions (#374) John Preston
* ae3d42a AWS Lambda Layer build and release (#371) John Preston
* 2b1c21b Adding macro image build phase and deploy template (#370) John Preston

0.11.0 (2021-01-14)
====================

First release of 2021 focusing on some new features / extension of existing features,
as well on improving stability.


New features
------------

885e89e - DB Secrets exposable to services (#356) (John Preston)
b723cc7 - Allow to override subnets to use for resources deployed inside VPC (#353) (John Preston)
0c6c86c - Create PrefixList for VPC and suibnets when creating a new VPC (#352) (John Preston)
4405fef - Support for ElasticCache Cluster via x-elasticache (#350) (John Preston)
59ceae0 - Added support for CodeGuru Profiling Group (#323) (John Preston)
97529fa - x-docdb support for DBClusterParameterGroup (#349) (John Preston)
a8888b6 - Extending ecs-plugin x-fields support (#336) (John Preston)

Improvements
-------------

faed0d3 - Align to CamelCase for x-scaling and x-network settings (#347) (John Preston)
249ba18 - Moved defauls into properties dicts. Added more docstrings for clarity (#345) (John Preston)
97345c7 - Pyup/updates (#329) (John Preston)
774640b - Create pyup.io config file (#327) (pyup.io bot)


Fixes
------
8d14ac0 - Fix for use_cloudmap (#346) (John Preston)
aa1ba40 - Fixed properties update (#344) (John Preston)
d2cd544 - Fixing VPC related settings (#341) (John Preston)


0.10.0 (2020-12-13)
====================

New features
------------

* 976e5bb Support for env_file (#318)
* a432763 Import simple SAM IAM policies templates. (#316)
* db2c8fe Support for service-to-service explicit ingress (#300)
* fe1e0af Added to support DB Snapshot for new DB creation (#297)
* 73cdf9a x-vpc - Support for VPC FlowLogs (#296)
* b9f1ec8 Scaling rules for Lookup queues (#293)
* 54faa50 Feature x-dns::Records to add Public DNS Records pointing to elbv2 (#289)
* d5a97a1 Adding support for kinesis streams (#287)

Improvements
-------------------

* 1be3b99 Improved secrets JsonKeys based on suggestions (#322)
* 6302bc6 x-rds:: Refactor Properties/MacroParameters/Settings (#309)


Fixes
------

* 191d420 No interpolate ${AWS::PseudoParameters} (#324)
* de87457 Bug fixes for RDS/DocDB and ECS containers (#305)
* 4220d7d TMP solution pending AWS official XRay publish (#304)
* 2c1fcfc Fix/duplicate secrets keys (#303)
* 4befc25 Fixed backward logic (#301)


Other updates and corrections
------------------------------

* 31d7bcc Added kinesis docs (#313)
* 997f0d9 Added back exports but not using in ComposeX. For cross-stacks usage (#310)
* cb0be55 Linted up code (#307)
* 5e559f0 Prefixing the log group with the root stack name for uniqueness (#295)
* c81f443 Refactored to single function recursively evaluating properties (#291)
* 16a5d39 Code linting (#285)


0.9.0 (2020-11-26)
==================

New features
------------

* cabd793 - Support for networks: and mapping to additional subnets. (#282)
* ba4ed5c - ECS Scheduled tasks support (#280)
* 82e2086 - Defaulting to encrypted for RDS (#276)
* a516a09 - Added support for service level x-aws keys from ecs-plugin (#273)
* 5e1ab08 - Improved logging settings (#265)
* 96ad398 - x-secrets::Lookup (#256)
* dfb249c - Lookup for ACM working (#254)
* ea6e05c - Feature x-docdb (#252)
* 0a4d258 - Refactor services to root stack (#248)
* 49a9d31 - ARN of TGT Group always passed to service stack (#245)
* eafcd38 - Updated documentation (#236)
* aa4c96b - Feature x-elbv2 with x-acm support and validation via x-dns (#228)
* fb0bc4a - Allowing RoleArn in x-rds Lookup (#233)
* 22feb56 - Lookup via resources tag api for VPC resources (#231)
* be536c1 - Cross-Cccount assume role generally and locally for lookup (#229)
* 32075f2 - Allow for custom cooldown for steps (#221)
* ca89836 - Upgrading troposphere==2.6.3 (#216)
* 3a1b0c8 - Linting DynDB features and use-case files (#213)
* 67cc67e - Feature x-s3 (#196)
* 230a9d3 - Lookup RDS DB/Clusters and secrets (#211)

Fixes
-----
* fc55f4b - Patched version of 0.8.9 with previews for 0.9.0 (#275)
* 1dc4113 - Replaced LOG.warn with LOG.warning (#271)
* 42c7027 - Docs improvements (#278)
* 78bef91 - Clarified Ingress syntax (#261)
* af31f33 - Fixed a number of small issues (#259)
* 02da4e1 - Hotfix services attributes (#243)
* fb7265a - During PyCharm refactor, error change occured (#238)
* c46c208 - Fixing import export string (#224)
* 7669799 - Removing missed print (#217)
* 4171044 - Fixing condition when QueueName property is set (#210)
* 0ced643 - Patched SQS based scaling rule and alarm (#202)

Syntax changes from previous version
------------------------------------

* 86d2141 - Refactor/services xconfig keys (#269)
* 1cfa6b7 - Refactor AppMesh properties keys (#262)
* d753473 - Refactor to classes for XResources and Compose resources (#219)


Documentation theme changed to Read The Docs and tuned some colors.


0.8.0 (2020-10-09)
==================

New features:
--------------
* `Support for ECS Scaling based on SQS Messages in queue <https://github.com/compose-x/ecs_composex/pull/194>`_
* `Support for ECS Scaling based on Service CPU/RAM values (TargetTracking) <https://github.com/compose-x/ecs_composex/issues/188>`_
* `Support for using existing Secrets in AWS Secrets Manager <https://github.com/compose-x/ecs_composex/pull/193>`_
* `Support for Service logs expiry from compose definition <https://github.com/compose-x/ecs_composex/issues/165>`_
* `Enable to use AWS CFN native PseudoParameters in string values <https://github.com/compose-x/ecs_composex/issues/182>`_
* `Improved Environment variables interpolation to follow the docker-compose behaviour <https://github.com/compose-x/ecs_composex/issues/185>`_


Closed reported issues:
------------------------
* https://github.com/compose-x/ecs_composex/issues/175

Some code refactor and bug fixes have gone in as well to improve stability and addition of new services.


0.7.0 (2020-08-12)
===================

New features:

* `Support for AWS Secrets mapping to secrets in docker-compose <https://github.com/compose-x/ecs_composex/pull/142>`_
* Support for `Use` on VPC which needs no lookup
* Support for IAM policies to manually add ad-hoc permissions outside of the pre-defined ones
* Additional configuration file to use with CodePipeline

Various bug fixes and some small features to help making plug-and-play easier.
Introduction to `Use` which should allow for resources reference outside of your account
without cross-account lookup.


0.6.0 (2020-08-03)
===================

New features:
* `Docker-compose multi-files (override support) <https://github.com/compose-x/ecs_composex/issues/121>`_

The new CLI uses positional arguments matching a specific command which drives what's executed onwards.
Trying to re-implement features as close to the docker-compose CLI as possible.

* **config** allows to get the YAML file render of the docker-compose files put together.
* **render** will put all input files together and generate the CFN templates accordingly.
* **up** will deploy do the same as render, and deploy to AWS CFN.


0.5.3 (2020-07-30)
==================

A lot of minor bug fixes and removing CLI commands to the benefit of better implementation via the compose file.

0.5.2 (2020-07-30)
==================

New features:

* `Support for AWS KMS <https://github.com/compose-x/ecs_composex/issues/77>`_

The support for KMS will be extended to use the CMK for RDS/SQS/SNS and any resource that can use KMS for encryption
at rest.

.. hint:: Mind, this might occur a few extra costs.


0.5.1 (2020-07-28)
===================

Small bug patches and code refactoring.
SQS now into a single stack unless there are more than 30 queues.

0.5.0 (2020-07-27)
==================

New features
------------

* `DynOAamoDB support <https://github.com/compose-x/ecs_composex/issues/31>`_
* Lookup for existing tables which the services get IAM access to.

0.4.0 (2020-07-20)
==================

* `ACM Support for ALB/NLB for public services. <https://github.com/compose-x/ecs_composex/issues/93>`_
* `AWS AppMesh support <https://github.com/compose-x/ecs_composex/issues/57>`_
* Attempt to making navigation through docs better.
* Automatic release to https://nightly.docs.ecs-composex.lambda-my-aws.io/ from master

To help with code quality and support, I subscribed to the following services:

* `CodeScanning using SonarCloud.io <https://sonarcloud.io/dashboard?id=lambda-my-aws_ecs_composex>`_
* `CodeCoverage reports with Codecov <https://codecov.io/gh/lambda-my-aws/ecs_composex>`_


0.3.0 (2020-06-21)
==================

Refactored the way the services, task definitions and containers are put together, in order to support multiple new features:

* `Allow multiple services to be merged into one Task definition <https://github.com/compose-x/ecs_composex/issues/78>`_
* `Support Docker compose v3 compute definition <https://github.com/compose-x/ecs_composex/issues/32>`_

The support for Docker compose compute settings allows to add up all the CPU / RAM of your service(s) and identify the
closest Fargate CPU/RAM configuration for the **Task Definition** (the respective CPU/RAM of each task is unchanged).


The docker-compose file is now more strictly close to the definition set in Docker Compose, with regards to attributes
and their expected types.

.. note::

    In order to respect more closely the docker-compose definition, the key previously used **configs** now is **x-configs**

0.2.3 (2020-04-16)
==================

Refactored the ecs part into a class and reworked the configuration settings to allow for easier integration.
Documentation has been updated to reflect the changes in the structure of the configs section.

New features
-------------

* Enable AWS X-Ray (`#56 <https://github.com/compose-x/ecs_composex/issues/56>`_)
    Enabling X-Ray will allow developer to get APM metrics and visualize the application interaction with other
    services.

* No-upload (`#64 <https://github.com/compose-x/ecs_composex/issues/64>`_)
    This allows to store the templates locally only.

    .. note::

        The templates are still validated from their body

* IAM Boundary for the IAM roles (`#55 <https://github.com/compose-x/ecs_composex/issues/55>`_)
    Permissions boundary are an IAM feature that allows to set boundaries which superseed other permissions associated
    to the entity. It is often the put as a condition for users creating roles to assign a specific Permission Boundary
    policy to the roles created.


0.2.2 (2020-04-10)
==================

Refactor of the ECS service template into a single class (still got to be reworked).
Refactored the ECS Services into a master class which ingests the CLI kwargs directly.

Reworked and reorganized documentation to help with readability

0.2.1 (2020-05-03)
==================

Code refactored to allow a better way to go over each template and stack so everything is treated in memory
before being put into a file and uploaded into S3.

* Issues closed
    * Docs update and first go at IAM perms (`#22`_)
    * Refactor of XModules logic onto ECS services (`#39`_)
    * Templates & Stacks refactor (`#38`_)
    * Update issue templates for easy PRs and Bug reports
    * Added `make conform` to run black against the code to standardize syntax (`#26`_)
    * Allow to specify directory to write all the templates to in addition to S3. (`#27`_)
    * Reformatted with black (`#25`_)
    * Expand TagsSpecifications with x-tags (`#24`_)
    * Bug fix for root template and Cluster reference (`#20`_)

Documentation structure and content updated to help navigate through modules in an easier way.
Documented syntax reference for each module

New features
-------------

* `#6`_ - Implement x-rds. Allows to create RDS databases with very little properties needed
    * Creates Aurora cluster and DB Instance
    * Creates the DB Parameter Group by importing default settings.
    * Creates a common subnet group for all DBs to run into (goes to Storage subnets when using --create-vpc).
    * Creates DB username and password in AWS SecretsManager
    * Applies IAM permissions to ECS Execution Role to get access to the secret
    * Applies ECS Container Secrets to the containers to provide them with the secret values through Environment variables.


0.1.3 (2020-04-13)
==================

A patch release with a lot of little features added driven by the writing up of the blog to make it easier to have in
a CICD pipeline.

See overall progress on `GH Project`_

Issues closed
--------------

* `Issue 14 <https://github.com/compose-x/ecs_composex/issues/14>`_
* `Issue 15 <https://github.com/compose-x/ecs_composex/issues/15>`_


0.1.2 (2020-04-04)
==================

Patch release aiming to improve the CLI and integration of the Compute layer so that the compute resources creation
in EC2 are standalone and can be created separately if one so wished to reuse.

Issues closed
-------------

 `Issue <https://github.com/compose-x/ecs_composex/issues/7>`_ related to the fix.

 `PR <https://github.com/compose-x/ecs_composex/pull/8>`_ related to the fix.

0.1.1 (2020-04-02)
==================

Added tags definition from Docker ComposeX with the x-tags which allows to add tags
to all resources that support tagging from AWS CFN

.. code-block:: yaml

    x-tags:
      - name: TagA
        value: SomeValue
      - name: CostcCentre
        value: IamNotPayingForThis
      - name: Some:Special:Key
        value: A long weird value

or alternatively in an object/dict format

.. code-block:: yaml

    x-tags:
      TagA: ValueA
      TagB: ValueB

0.1.0 (2020-03-24)
==================

* First release on PyPI.
    * Working VPC + Cluster + Services
    * Working expansion of existing Cluster with new VPC
    * Working expansion of existing VPC and Cluster with new services
    * IAM working to allow services access to SQS queues
    * SQS Queues functional with DLQ
    * Works on Python 3.6, 3.7, 3.8
    * Working start of build integration in CodeBuild for automated testing


.. _GH Project: https://github.com/orgs/lambda-my-aws/projects/3

.. _#22: https://github.com/compose-x/ecs_composex/issues/22
.. _#39: https://github.com/compose-x/ecs_composex/issues/39
.. _#38: https://github.com/compose-x/ecs_composex/issues/38
.. _#27: https://github.com/compose-x/ecs_composex/issues/27
.. _#26: https://github.com/compose-x/ecs_composex/issues/26
.. _#25: https://github.com/compose-x/ecs_composex/issues/25
.. _#24: https://github.com/compose-x/ecs_composex/issues/24
.. _#20: https://github.com/compose-x/ecs_composex/issues/20
.. _#6: https://github.com/compose-x/ecs_composex/issues/6
