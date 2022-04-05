# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>


from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Output, Ref, Sub
from troposphere.iam import Role as IamRole

from ecs_composex.common.cfn_params import Parameter
from ecs_composex.ecs.ecs_params import CLUSTER_NAME, EXEC_ROLE_T, TASK_ROLE_T
from ecs_composex.iam import service_role_trust_policy
from ecs_composex.iam.iam_params import IAM_ROLE, IAM_ROLE_ARN, IAM_ROLE_ID
from ecs_composex.iam.iam_params import MAPPINGS_KEY as IAM_MAPPINGS_KEY


class EcsRole:
    """
    Class to wrap around the AWS IAM Role
    """

    def __init__(self, family, role_type):
        """
        :param family: The family the role will belong to
        """
        if role_type not in [TASK_ROLE_T, EXEC_ROLE_T]:
            raise ValueError(
                "role_type is", role_type, "expected one of", [TASK_ROLE_T, EXEC_ROLE_T]
            )
        self._role_type = role_type
        self._name = None
        self._arn = None
        self.family = family
        self.stack = None
        self.logical_name = f"{self.family.logical_name}{role_type}"
        self.cfn_resource = None
        self.init_role(role_type)
        self.mapping_key = IAM_MAPPINGS_KEY

        self.output_properties = {
            IAM_ROLE: (self.logical_name, self.cfn_resource, Ref, None),
            IAM_ROLE_ID: (
                f"{self.logical_name}{IAM_ROLE_ID.return_value}",
                self.cfn_resource,
                GetAtt,
                IAM_ROLE_ID.return_value,
            ),
            IAM_ROLE_ARN: (
                f"{self.logical_name}{IAM_ROLE_ARN.return_value}",
                self.cfn_resource,
                GetAtt,
                IAM_ROLE_ARN.return_value,
            ),
        }
        self.attributes_outputs = {}
        self.outputs = []
        self.lookup = {}

    @property
    def name_param(self):
        """
        Returns the pointer to the ECS IAM Role Name to use.
        """
        if self._name is None or not self.attributes_outputs:
            self.generate_outputs()
            self._name = self.attributes_outputs[IAM_ROLE]["ImportParameter"]
        return self._name

    @name_param.setter
    def name_param(self, value):
        self._name = value

    @property
    def name(self):
        """
        Returns the Ref() on the name parameter
        """
        return Ref(self.name_param)

    @property
    def output_name(self):
        """
        The pointer on  output name from the IAM stack to use
        """
        if not self._name:
            return None
        return GetAtt(self.mapping_key, f"Outputs.{self.name_param.title}")

    @property
    def arn_param(self):
        """
        Returns the pointer to the ECS IAM Arn to use
        """
        if self._arn is None or not self.attributes_outputs:
            self.generate_outputs()
            self._arn = self.attributes_outputs[IAM_ROLE_ARN]["ImportParameter"]

        return self._arn

    @arn_param.setter
    def arn_param(self, value):
        self._arn = value

    @property
    def arn(self):
        """
        Return Ref() on arn parameter property
        """
        return Ref(self.arn_param)

    @property
    def output_arn(self):
        """
        Returns the pointer on the IAM Role ARN from the IAM stack
        """
        if not self.arn_param:
            raise AttributeError(f"{self.family} - ARN Role attribute not yet set")
        return GetAtt(self.mapping_key, f"Outputs.{self.arn_param.title}")

    def init_role(self, role_type):
        """
        Initialize the new IAM Role and based on the use for it, sets defaults IAM policies.
        """
        if role_type == EXEC_ROLE_T:
            self.cfn_resource = IamRole(
                self.logical_name,
                AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
                Description=Sub(
                    f"Execution role for {self.family.logical_name} in ${{{CLUSTER_NAME.title}}}"
                ),
                ManagedPolicyArns=[],
                Policies=[],
            )
        elif role_type == TASK_ROLE_T:
            self.cfn_resource = IamRole(
                self.logical_name,
                AssumeRolePolicyDocument=service_role_trust_policy("ecs-tasks"),
                Description=Sub(
                    f"TaskRole - {self.family.logical_name} in ${{{CLUSTER_NAME.title}}}"
                ),
                ManagedPolicyArns=[],
                Policies=[],
            )

    def set_new_resource_outputs(self, output_definition):
        """
        Method to define the outputs for the resource when new
        """
        if output_definition[2] is Ref:
            value = Ref(output_definition[1])
        elif output_definition[2] is GetAtt:
            value = GetAtt(output_definition[1], output_definition[3])
        elif output_definition[2] is Sub:
            value = Sub(output_definition[3])
        else:
            raise TypeError(
                self._name,
                f"3rd argument for {output_definition[0]} must be one of",
                (Ref, GetAtt, Sub),
                "Got",
                output_definition[2],
            )
        return value

    def generate_outputs(self):
        """
        Method to create the outputs for XResources
        """
        if self.stack and not self.stack.is_void:
            root_stack = self.stack.title
        else:
            root_stack = self.mapping_key
        for (
            attribute_parameter,
            output_definition,
        ) in self.output_properties.items():
            output_name = f"{self.logical_name}{attribute_parameter.title}"

            value = self.set_new_resource_outputs(output_definition)
            self.attributes_outputs[attribute_parameter] = {
                "Name": output_name,
                "Output": Output(output_name, Value=value),
                "ImportParameter": Parameter(
                    output_name,
                    group_label="ECS IAM Settings",
                    return_value=attribute_parameter.return_value,
                    Type=attribute_parameter.Type,
                ),
                "ImportValue": GetAtt(
                    root_stack,
                    f"Outputs.{output_name}",
                ),
                "Original": attribute_parameter,
            }
        for attr in self.attributes_outputs.values():
            if keyisset("Output", attr):
                self.outputs.append(attr["Output"])
