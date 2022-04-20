
.. meta::
    :description: ECS Compose-X AWS OpenSearch syntax reference
    :keywords: AWS, AWS ECS, Docker, Compose, docker-compose, AWS OpenSearch, ElasticSearch

.. _opensearch_syntax_reference:

==============
x-opensearch
==============

Allows you to create / lookup OpenSearch Domains to use with your ECS Services.

.. hint::

    Given the combinations of settings that only work together, we have implemented validations to verify those early.
    If we missed something, please `report an issue in GitHub `_

Syntax
=======

.. code-block:: yaml

    x-opensearch:
      opensearch-01:
        Properties: {}
        Settings: {}
        Services: {}
        Lookup: {}
        MacroParameters: {}

.. tip::

    For production workloads, to avoid any CFN deadlock situations, I recommend you generate the CFN templates for opensearch,
    and deploy the stacks separately. Using Lookup you can use existing DocDB clusters with your new services.

.. seealso::

    For more structural details, see `JSON Schema`_

Properties
===========

Refer to the `AWS OpenSearch Domain CFN Properties`_.

.. attention::

    The OpenSearch properties are very tedious, not all instance types support the same settings (EBSOptions etc.).
    Therefore, ECS Compose-X will try to autocorrect the settings **based on the instance types set**.
    However, if it cannot solve the issue due to too incompatible settings contradicting each other, it will fail.

    Refer to the `Instance Types supported by OpenSearch`_ to check out these settings.

.. hint::

    ECS Compose-X does an instance-types verification to ensure you are not mixing normal and Graviton instance types.

.. hint::

    ECS Compose-X will try to autocorrect the following properties based on the Instance Type

    * OpenSearch domain version
    * EBSOptions
    * EncryptionAtRestOptions
    * AdvancedSecurityOptions
    * ClusterConfig.WarmEnabled

    When possible, it will just void / set to False the offensive setting to the instance type.


VPCOptions
------------

Whenever you set the VPCOptions, Compose-X will create a new AWS EC2 Security Group in order to manage the Ingress defined
from the other services. When these are set, ECS Compose-X will deal with setting Security Group ingress.

.. attention::

    When setting the VPCOptions, you cannot set more Subnets than you set the total number of instances for the domain.
    For example, if you set only 1 Instance (i.e. for the master) then you can only set 1 Subnet in the SubnetIds.

MacroParameters
================

These parameters will allow you to define extra parameters to define your cluster successfully.

.. code-block:: yaml

    Instances: []
    DBClusterParameterGroup: {} # AWS DocDB::DBClusterParameterGroup properties

CreateLogGroupsResourcePolicy
-------------------------------

When set to True, it will create a new AWS::Logs::ResourcePolicy (10 per accounts limit) that will grant the
AWS OpenSearch Service to write to AWS CloudWatch Logs.

If you never had set this up, turn set it to True. However, if you already have your own policy in place, you can
use that, simply ensure that the permissions will allow your domain to write to these.

.. tip::

    If no resource policy is set to allow the domain to write to the logs, or is disabled, creation of the domain will
    fail.

CreateLogGroups
----------------

When set to True, it will automatically create **all** log groups for the given domain to write to.
When set as a list, each value it must be one of

* "SEARCH_SLOW_LOGS"
* "ES_APPLICATION_LOGS"
* "INDEX_SLOW_LOGS"
* "AUDIT_LOGS"

For each of the value enabled above, it will create a new Log Group.

.. attention::

    When settings AUDIT_LOGS make sure to enable the appropriate security options.

RetentionInDays
----------------

Allow to define the retention in days value for the new log groups getting created.

GenerateMasterUserSecret
-------------------------

This allows to automatically create a new AWS SecretsManager secret, with a username and password, that you
can use to then authenticate and administer the domain with.


CreateMasterUserRole
---------------------

When set to True, allow to create an IAM role (instead of secret) that your account can assume in order then to administer
the domain

.. hint::

    You can set GenerateMasterUserSecret or CreateMasterUserRole, but not both, to True

MasterUserRolePermissionsBoundary
-----------------------------------

Allows you to define IAM Permissions Boundary when creating the new AWS IAM MasterRole

Services
========

The syntax for listing the services remains the same as the other x- resources.

.. code-block:: yaml

    Services:
      <service/family name>
        Access:
          Http: [RO|RW]
          DBCluster: [RO|RW]

Access types
------------

Http
^^^^^^^^

This defines the Http permissions that you wish to grant your service to perform queries to the OpenSearch domain

DBCluster
^^^^^^^^^^

This defines the IAM permissions you wish to grant to the service that will allow to describe and discover the
OpenSearch domain

.. literalinclude:: ../../../ecs_composex/opensearch/opensearch_perms.json
    :language: json


Settings
========

Subnets
-----------

This parameter allows you to define which subnets group you wish to deploy OpensSearch to. If the `VpcOptions`_ were
not set in the `Properties`_ then they automatically get added.

Lookup
========

Lookup for OpenSearch domains is available. However not used / tested with legacy ElasticSearch domains.

Examples
========

.. literalinclude:: ../../../use-cases/opensearch/create_only.yml
    :language: yaml
    :caption: Sample to crate two DBs with different instances configuration

.. literalinclude:: ../../../use-cases/opensearch/lookup_only.yml
    :language: yaml
    :caption: Create a DocDB and import an existing one.


JSON Schema
============

Model
--------

.. jsonschema:: ../../../ecs_composex/opensearch/x-opensearch.spec.json

Definition
------------

.. literalinclude:: ../../../ecs_composex/opensearch/x-opensearch.spec.json

Test files
===========

You can find the test files `here <https://github.com/compose-x/ecs_composex/tree/main/use-cases/opensearch>`__ to use
as reference for your use-case.


.. _AWS OpenSearch Domain CFN Properties: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-elasticsearch-domain.html
.. _VpcOptions: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-elasticsearch-domain-vpcoptions.html
.. _Instance Types supported by OpenSearch: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/supported-instance-types.html
.. _report an issue in GitHub : https://github.com/compose-x/ecs_composex/issues/new?assignees=JohnPreston&labels=bug&template=bug_report.md&title=%5BBUG%5D
