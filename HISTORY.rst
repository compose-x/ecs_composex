=======
History
=======

0.18.0 (2022-05-04)
=====================

It has been a long time since 0.17 has been released, and the subsequent patch releases have been resilient enough
to guide us to this point.

So May the 4th be with us all on this new release, packed with bug fixes, new features, and more to come!

New features
----------------

Some very exciting new features have come into this new version, and although only one new AWS Resource has
made it to the project, the most exciting change is the use of a module manager which if going to dynamically
load the core ECS Compose-X modules as well as extensions that anyone can write on their own, to support
further use-cases.

* c36a853 Adding documentation on creating new modules Further docs corrections (John Preston)
* 91a3962 Adding -p option, equivalent to -n, for project name (John Preston)
* eafdbb4 Adding label on tags parameters (John Preston)
* 47021cd TaskCompute class to manage CPU/RAM settings (John Preston)
* f1bdb5f Added x-kms to x-sqs support (John Preston)
* 8cb0edd x-cloudmap for x-resources (#584) (John Preston)
* b953169 Allows to define ports to allow for ext_sources and aws_sources (#582) (John Preston)
* bfb1a74 Added feature for RuntimePlatform Task definition settings (John Preston)
* 5a300eb Route53 stack created for records (John Preston)
* 9525f05 Added x-kms:: mapping to S3.BucketEncryption (John Preston)
* b1d6de2 Added x-neptune.Lookup (#565) (John Preston)

Breaking changes
--------------------

This new version comes with a few breaking changes :

* Deprecation of ``Use`` for resources, such as x-vpc, x-cluster, x-s3 and so on. The Use functionality was too limited.
* Deprecation of ``x-dns``, replaced with ``x-route53`` and ``x-cloudmap``
* ec24dd1 Remove prefix list given max size is immutable when set (John Preston)

To help with the transition to using the 0.18 version, an upgrade script has been created.

To use it, simply do

.. code-block:: bash

    python3 -m venv compose-x
    source compose-x/bin/activate
    pip install pip poetry -U
    git clone https://github.com/compose-x/ecs_composex
    cd ecs_composex/; poetry install
    ./upgrade_scripts/upgrade_to_0.18.py -h

    # for example
    ./upgrade_scripts/upgrade_to_0.18.py -f docker-compose.yaml


Geneal Improvements
-----------------------

These improvements have been made to make ecs-compose-x more reliable and consistent at validating
itself and getting closer to a proper production-grade tool.

* 9d9c57e Simplified JSON schema loading (John Preston)
* cb76c1a Using pyupgrade pre-commit hook (John Preston)
* e7ea8f0  (John Preston)
    * Allowing Env resources with _to_ecs to apply
    * Enforce x-cluster deprecation of Use * Improve migration script
* f3518be Refactoring x-route53 code into smaller modules (John Preston)
* ef0bca0 Lint code. Change x-cluster to add the exec bucket/key into x-s3/x-kms (John Preston)
* 1860d43 Linted code (John Preston)
* ac27461 Refactor to use modules more and cleanup params RES/MOD key (John Preston)
* 0b5d87b (John Preston)
    * Refactored resources stack to use the module from manager
    * Refactored x-cluster bucket/kms key to use x-kms/x-s3 properly
    * Fixed up use case tests * Refactored x-sns to not use x-sns.Topics{}
* a6b3685 Refactors and renames of ecs packages to improve ECS Family configuration (John Preston)
* c33d63f Using published first, target second when creating ingress rules (#589) (John Preston)
* bc2787d Refactor schemas files to be within module (#587) (John Preston)
* e32f92b Updated deps and NOTICES (John Preston)
* a11254b Simple upgrade script to 0.18 syntax (John Preston)
* bfab153 Updated test files with upgrade script (John Preston)
* ff6acd4 When secret JSON keys given, only expose those, remove default secret value (John Preston)
* 97907a1 Precaution for Name value in x-events (John Preston)
* 43c24be Removing tests for deprecated feature (John Preston)
* d558645 No more Zones defined in settings (John Preston)
* d7233b1 Refactored x_dependencies for x-rds (John Preston)
* b6d57de Updated JSON Specs (John Preston)
* 8f3b4b8 Refactored function to link x-resource to services for IAM and environment variables. Added typing for resource to service linking Link resource to services function deals with new vs lookup on its own (John Preston)
* 52d0771 Testing troposphere 4.0.0 beta Refactored env vars, only the Ref value is exposed by default (John Preston)
* 3b41ad6 Refactored to_ecs for RDS like resources (John Preston)
* 926ce99 Refactor x-alarms to x mapping (John Preston)
* 77b9dbd Refactored x_dependencies for x-rds (John Preston)
* 39ef236 Using retry on CFN validate template (John Preston)
* 29fea25 Updating CICD. Macro will be moved elsewhere (John Preston)
* b52a568 Updated neptune for creation and added test case (John Preston)
* 3c9cc03 Reworked lookup resources.kms policies assignment (John Preston)
* 8d345b1 Simplified _to_ecs functions and added tests cases (John Preston)
* 9ec1dde Refactored x-s3 to use generic IAM policies functions (John Preston)
* 233d973 Strenghtening Lookup JSON model (John Preston)
* 14bcb48 pre-commit cleanup (John Preston)
* 5057944 Updated copyright dates (John Preston)
* c55e27c Updated userpool mappings (John Preston)
* ce6b049 Updated ACM, cloudmap and other settings (John Preston)
* 361ac79 Reworked x-route53 with ACM and ELBv2 (John Preston)
* 78e3ced Reworked x-dns to x-route53 and x-cloudmap (John Preston)
* 3de79c5 Refactoring ELBv2 for external support (John Preston)
* 0cf307a Reworked ECS IAM Roles and Family init (John Preston)
* 9891e4f Reworking the XResources classes (John Preston)
* 2df8b24 Re-instating default PrivateNamespace to support all DNS features (#571) (John Preston)
* 2745038 Refactoring / cleaning the compose and ECS services related settings (#568) (John Preston)
* 4bac941 Use official nginx-prometheus-exporter image (#570) (Luca Comellini)


Bug Fixes
----------

A number of these bug fixes are the result of changes in the general improvements above,
which mostly were due to restructuring of the code and classes.

* fcddf63 Fix ECS Log group name (John Preston)
* bf44bfd Fixed x-cluster logging configuration (#595) (John Preston)
* cbd1546 Fix for x-route53 circular imports (John Preston)
* c6c5db6 Fix for duplicate secret var names (John Preston)
* 690c55a Fixing x-rds.Lokup.db and x-neptune.Lookup (#593) (John Preston)
* 88f0697 Fix networks{} to subnets association (John Preston)
* 023a555 Fix cloudmap to ecs (John Preston)
* 84c7cc5 Fix RAM GB conversion to MB (John Preston)
* a445e6b Fix imports (John Preston)
* a96d565 Network feature and compute settings fixes. (#591) (John Preston)
* 2cfd6f3 Fixing logging. Working traefik public e2e (John Preston)
* 431309d Fixing code smells (John Preston)
* eb432a6 Fix Launch Type and set it early Fix min CPU for ECS Auto-fix feature for ECS cluster providers Common class for sidecars (John Preston)
* 4ce25d9 Split refactor of ecs_prometheus and sidecars (John Preston)
* ee5d386 Fixing a non-problem for non-secret value (John Preston)
* 23ec4c8 Split x-elbv2 into modules and fix for env vars (John Preston)
* fd1d0bc Fix services add and split-refactor compose.x_resources (John Preston)
* ea9b56f Fixing port mappings, adding protocol support and fargate default (#588) (John Preston)
* f00f0af Fix services scaling and improve input validation (John Preston)
* 72f1cd2 Fix x-events input from services output (John Preston)
* 5a3a92e Fixing up condition where template is in fact not needed (John Preston)
* ab327cb Align the code to the JSON Schema specs (John Preston)
* 1798a25 Fix x-events multi events on same service and efs bug (John Preston)
* db57b4b Fixed x-alarms to x-elbv2 Dimensions (John Preston)
* 69db70a Fixing up RDS and DB Version for testing (John Preston)
* b4a8e5d Fixed ELBv2 - Alarms (John Preston)
* 0c0e60c Fixed ELBv2 - Cognito mapping (John Preston)
* 6fec8fc Fix and simplified resource to services container env vars (John Preston)
* dc351a8 Fix SSM ARN parameter (John Preston)
* a09f17e Fixing volumes settings and handle host config (John Preston)
* d2de0a6 Fixes in RDS like resources (John Preston)
* 73f43d1 Fixed up x-acm to x-elbv2. Got generic algorithm for x-to-x resources (John Preston)
* 96ad4c5 Fixes and log formatting (John Preston)
* 6edf0f2 Fix x-ssm_parameter (John Preston)
* 3980975 Fixed x-events and x-elbv2 (John Preston)


0.17.0 (2021-10-20)
====================

This new release comes with a lot of changes and fixes that aim to both give more CFN native support and equally
allow for future features to be integrated in a better way.

A lot of changes on the modules one want to implement to support new AWS resources is greatly simplified.


Breaking changes
-----------------

Compute platform options
^^^^^^^^^^^^^^^^^^^^^^^^^^

In this new version we have deprecated the --spot-fleet (#501) option. Users who want to use EC2 for the deployment
of their services will be in charge of settings it all up on their own to fit their requirements.

This was then done after implementing (#500) which will allow through Lookup to detect the ECS Cluster compute
settings and automatically set the Launch Platform for the services appropriately. Users can, if they have
a cluster with multiple capacity providers override and set what capacity provider to use for the service.
Again, if that is not available in the cluster (using Lookup) then it will either fail or fallback to a working
capacity provider.


IAM stack created at the root
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This change **should not** be incurring any change to existing stacks **if the IAM permissions were stricly managed under Compose-X**.
A new *iam* stack is created with all the IAM roles of the services (Task and Execution Role) which is then passed on to the other
nested stacks that will need it.

This change is necessary for upcoming features support and changes.

That change also helps with a simpler way to manage IAM policies for the roles and a more flexible way to set permissions that does
not require to wait for the service nested stack to complete to possibly set IAM permissions or get the roles names/arns.


New features
-------------

* 2fcd1ba Added x-alarms and x-elbv2 cross-support Updated x-alarms docs (John Preston)
* 65d4123 Feature x-ecs enable exec (#539) (John Preston)
* 51a4628 Allow to add custom and predefined bucket policies (John Preston)
* 599b5ad Refactor IAM to set roles in their own stack (#532) (John Preston)
* c9564ee Added support for Conditions in Listener target to cover native CFN implementation (John Preston)
* 8bdf95d Allowing for resource to have an ARN extension from policy definition (#535) (John Preston)
* b39859c Added option to store SSM parameter as Base64 to avoid invalid characters (#527) (John Preston)
* 3cc0908 x-elbv2 Target Group Attributes support (#518) (John Preston)
* 41d393f Feature - docker working_dir (#509) (John Preston)
* ee82fef Feature services.x-ecs to enable services level capacity providers (#507) (John Preston)
* 5ec5c1f Option to enforce secure connection to S3 bucket for IAM role (#504) (John Preston)
* f5ca17d Added ecs.ephemeral.storage label to extend Fargate local storage (#503) (John Preston)
* 6fe4880 JSON validation for more x-resources (#502) (John Preston)
* a399344 Deprecating --spot-fleet (#501) (John Preston)
* 0141544 Adds deploy label ecs.compute.platform to override from FARGATE (#500) (John Preston)


Fixes
-------

* 7202741 Fix release 0.16.10 (#530) (John Preston)
* 84c3716 Fix ACM and Rules conditions (#529) (John Preston)
* 8c20f82 Fix SSM ARN and volumes path (#528) (John Preston)
* aac5811 Fix release/0.16.9 (#526) (John Preston)
* 5cd37a5 Fixing IAM issues (#525) (John Preston)
* 455b3d4 Fix release/0.16.8 (#524) (John Preston)
* 84cd54d Fix missing lookup mappings (#523) (John Preston)
* 760e804 Fix release - v0.16.7 (#522) (John Preston)
* c8e8882 Fix for kms key alias in x-s3 Lookup (#521) (John Preston)
* f223bb5 Fix for x-kms Lookup (John Preston)
* 900b03e Fix release 0.16.4 (#517) (John Preston)
* b9c4ac5 Fix settings typo (John Preston)
* 79012d7 [FIX] ecs placements condition (#514) (John Preston)
* 898ec07 Fix release to 0.16.3 (#511) (John Preston)
* 88ce644 Fixes for ECS and Cognito (#510) (John Preston)
* 197bf3b Fixing docker-compose commands for any env (John Preston)


Improvements
--------------

* 84f7216 Update deps (John Preston)
* f8bdd6c When services have an expose set of ports, allowing self-ingress (John Preston)
* 403a652 Updated docs (John Preston)
* decd5c2 Flake8'd the code (John Preston)
* 2fcd1ba Added x-alarms and x-elbv2 cross-support Updated x-alarms docs (John Preston)
* 22cbd5a Import ecs_composex_specs schemas in main application (#538) (John Preston)
* ea510b4 Policies Uniqueness (John Preston)
* 6a6409d Working pre-defined bucket policies (John Preston)
* 1820fc3 Ensures the IAM policies are created before the service is (#534) (John Preston)
* 887d31b Reworked docs and added to docs (#519) (John Preston)
* bfed008 Refactor the services input (#516) (John Preston)
* 66e2733 Update issue templates (John Preston)
* dc7b713 Refactor - perform x-resources.Lookup early (#508) (John Preston)
* 8dfa8a3 Adding non-docker command (John Preston)
* 40153f7 Using poetry to manage dependencies (John Preston)



0.16.0 (2021-08-19)
======================

This release adds features that revolve around the monitoring of applications by supporting
Prometheus and AWS CloudWatch integration integration making it easy for users to collect metrics
for Prometheus enabled applications.

It also improves the docker experience for users that wish to automatically use the docker image digest instead of tags,
and for users of AWS ECR, allows to perform an image scan of the indicated image prior to continue the process.

Fixed docs and trying to steer towards a CLI usage with docker for new starters to avoid python environments problems.

New features
--------------

* b81d444 x-alarms schema validation (#494) (John Preston)
* 604dbfe docker images digest substitution (#492) (John Preston)
* a2c740e Battletesting prometheus and EMF processors (#491) (John Preston)
* f19899b Adding docs, tests, and lib dependency to enable prometheus (#488) (John Preston)
* c67d3c9 Adding some prometheus support (#472) (John Preston)
* d92a1ca Adding x-ssm_parameters macro parameters (John Preston)
* e956203 Better ECR display conditions (John Preston)
* ae10da7 Add successful notice output for ECR Scan (John Preston)
* b307f6d Feature - x-ssm (#486) (John Preston)
* de345c1 Feature x-ecr interpolate digest (#482) (John Preston)
* c448650 Adding ECR Scan at execution time (#478) (John Preston)
* cd441d8 Adding x-dashboards feature (#476) (John Preston)
* 6c2e95e Cognito ALB app profile creation (#475) (John Preston)
* 9ae02ff Feature - Lookup codeguru profiler (#468) (John Preston)
* 56156b0 Using codeguru at top level (#462) (John Preston)
* 1e6016a CLI Feature: `plan` (#459) (John Preston)

Improvements
-------------

* 381aab9 Adding ECR Scan reporter lib to CLI and macro (John Preston)
* 3650792 Matching PEP0440 RC syntax (John Preston)
* dc903fb Changing docs theme (John Preston)
* 25b3e7b Using poetry env commands to make life easier (John Preston)
* 507b917 Pyproject black settings update (John Preston)
* 024852f Fixes and new features to help with life comfort (John Preston)
* 2d778d2 Updated deps (John Preston)
* fadab75 Updating dependency (John Preston)
* fd99dbb Using more of common compose_x lib (John Preston)
* cef8f1e Removing cognito init override (John Preston)
* 6aa54ea Not using sphinx-material to generate sitemap.xml (John Preston)
* b5e1d63 Using common lib for keyisset and keypresent (John Preston)
* 043d787 use Poetry and pyproject.toml (#483) (John Preston)
* 7aff79e Added x-ecr docs for scans (#479) (John Preston)
* 79c3346 Addind DL stats. (John Preston)
* 280b0f6 Newer docker image source (John Preston)
* dbfd70c Docs improvements (#467) (John Preston)


Fixes
------

* 923ee23 Fixing docs(#497) (John Preston)
* 2a7cc3e Adding exception for bucket init creation in us-east-1 (#496) (John Preston)
* 8c6a159 Fix/subnets must belong to same vpc (#493) (John Preston)
* d2d9ba4 Fix missing return and outputs for new SSM Parameters (John Preston)
* 42b442f Fix docs buildspec (John Preston)
* 6297604 Fix layer buildspec (John Preston)
* 7c72014 Fixing build for docs and manifest (John Preston)
* 7da9538 Indentation fix (John Preston)
* 2390d23 Fixing loop and scan report return (#480) (John Preston)
* 14de30c Fixing setup.py for extra (John Preston)
* 3b30cf7 Fixing pyproject version (John Preston)
* 3131973 Bug fixes (#473) (John Preston)
* 40d0195 Fixed missing env vars via lookup (#466) (John Preston)
* 6306ed0 Fixing S3 perms bug and adding s3 to JSON specs (#464) (John Preston)


0.15.0 (2021-05-13)
===================

Version 0.15.0 marks the start of using JSON Schema validation to validate
early the content of the Compose files.

The original compose-spec is updated with the varied x-resources and features,
source is taken from gh:compose-spec/compose-spec.

This will lead into better and easier long term maintenance of the input definition.
Eventually, a lot of the custom settings and classes will use models generated with
Pydantic.

New features
-------------

* 92e9d48 Using newer minimum definition (John Preston)
* 6c0688c Use schema validation to validate compose user-input. (#458) (John Preston)


Improvements
-------------

* ef01b4a Improving documentation (#457) (John Preston)
* 97c7b65 Adding region and randomness to composite alarm name (#455) (John Preston)
* b9a8399 Workaround limitation of 20 DB Parameters (Jack Saunders)
* 3c57cfe Adding CRUD policy template for s3 objects (John Preston)
* 94d868a Adding `Use` support to x-s3 (#450) (John Preston)
* 137a10c Using compose-x render lib to ingest multiple compose files content (#442) (John Preston)


Fixes
-----
* f7b5ccc Fix/alarm name should be consistent over updates (#456) (John Preston)
* 92e0693 CRUD policy patch (John Preston)
* b71f448 Adding forgotten CreateMultipartUpload (John Preston)
* 5493e6e Fixed families dependencies (#446) (John Preston)
* 51eb1cb Code formatting (John Preston)
* 69c5964 Fixing duplicate export names (#445) (John Preston)


0.14.0 (2021-03-23)
====================

Version 0.14.0 is a release coming with a new LICENSE attached, the Mozilla Public License 2.0 (MPL 2.0).

* 1e82eed LICENSE change to MPL-2.0 (John Preston)


New features
---------------
* 9fbe3aa New pre-defined alarms for services (#432) (John Preston)
* a6083d7 Added CompositeAlarm support (#431) (John Preston)


Fixes
-------
* 534dcd0 reversed conditions logic for IAM Role for SAR template (John Preston)
* 9f145cf Publish template for AWS SAR (#438) (John Preston)
* 8008043 Removing the scaling target and scaling policies (#436) (John Preston)
* 122efae Fixed output attribute name for S3 to RDS feature (#433) (John Preston)

Improvements
----------------
* 1eeb6f6 Upgrade to Troposphere 2.7.0 (John Preston)
* 2afec02 Improved macro settings override and layer key (#440) (John Preston)
* 51a568f new cfn-macro Parameter BucketName (#439) (John Preston)
* ef08ae9 New image URL for XRay (John Preston)
* 670bf27 Adding default prefix for default log group name (#428) (John Preston)



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
