Deploy to your AWS Account
============================

.. list-table::
    :widths: 50 50 50
    :header-rows: 1

    * - Region
      - Lambda Layer based Macro
      - Docker based Macro
    * - us-east-1
      - |LAYER_US_EAST_1|
      - |DOCKER_US_EAST_1|
    * - eu-west-1
      - |LAYER_EU_WEST_1|
      - |DOCKER_EU_WEST_1|

.. |DOCKER_US_EAST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/docker-macro.yaml

.. |DOCKER_EU_WEST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/docker-macro.yaml

.. |LAYER_US_EAST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/layer-macro.yaml

.. |LAYER_EU_WEST_1| image:: https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png
    :target: https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/new?stackName=compose-x-macro&templateURL=https://s3.eu-west-1.amazonaws.com/files.compose-x.io/macro/layer-macro.yaml
