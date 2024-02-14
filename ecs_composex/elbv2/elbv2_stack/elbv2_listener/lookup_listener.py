#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ecs_composex.elbv2 import Elbv2
    from ecs_composex.elbv2.elbv2_ecs import MergedTargetGroup
    from troposphere import Template

from compose_x_common.aws.elasticloadbalancing import LB_V2_LISTENER_ARN_RE
from compose_x_common.compose_x_common import keyisset, set_else_none
from troposphere import Ref
from troposphere.cognito import UserPoolClient
from troposphere.elasticloadbalancingv2 import ListenerRule

from ecs_composex.common import NONALPHANUM
from ecs_composex.common.aws import find_aws_resource_arn_from_tags_api
from ecs_composex.common.logging import LOG
from ecs_composex.elbv2.elbv2_stack.helpers import (
    LISTENER_TARGET_RE,
    define_actions,
    define_target_conditions,
    import_cognito_pool,
    map_service_target,
    validate_duplicate_targets,
)
from ecs_composex.resources_import import import_record_properties


class LookupListener:
    """Class to represent a Lookup listener"""

    targets_keys = "Targets"

    def __init__(self, lb: Elbv2, port: int, definition: dict):
        self._lb = lb
        self._port = port
        self._definition = definition

        self.arn: str = find_aws_resource_arn_from_tags_api(
            self.definition,
            self.lb.lookup_session,
            "elasticloadbalancing:listener",
        )
        assert LB_V2_LISTENER_ARN_RE.match(self.arn)

        client = self.lb.lookup_session.client("elbv2")
        self.properties: dict = client.describe_listeners(ListenerArns=[self.arn])[
            "Listeners"
        ][0]
        self.rules_r: list[dict] = client.describe_rules(
            ListenerArn=self.arn, PageSize=100
        )["Rules"]
        if self.lb.is_nlb():
            self.rules = self.rules_r
            self.default_rule = self.rules_r[0]
        else:
            unordered_rules: list[dict] = []
            for rule in self.rules_r:
                if rule["Priority"] == "default" or keyisset("IsDefault", rule):
                    self.default_rule: dict = rule
                else:
                    unordered_rules.append(rule)
            if not self.default_rule:
                raise LookupError(
                    "Failed to find default rule for {} - {}".format(
                        self.arn, unordered_rules
                    )
                )
            self.rules = sorted(
                unordered_rules, key=lambda _rule: int(_rule["Priority"])
            )
        self.tidy_targets()
        self.services = (
            self.definition[self.targets_keys]
            if keyisset(self.targets_keys, self.definition)
            and isinstance(self.definition[self.targets_keys], list)
            else []
        )

    def __repr__(self):
        return self.arn

    @property
    def Protocol(self) -> str:
        return self.properties["Protocol"]

    @property
    def Certificates(self):
        return set_else_none("Certificates", self.properties)

    @property
    def Port(self) -> int:
        return int(self.properties["Port"])

    @property
    def lb(self) -> Elbv2:
        return self._lb

    @property
    def port(self):
        return self._port

    @property
    def definition(self) -> dict:
        return self._definition

    @property
    def certificates(self):
        return set_else_none("Certificates", self.definition)

    @property
    def props(self) -> dict:
        return {"Definition": self.properties, "Rules": self.rules_r}

    def tidy_targets(self):
        LOG.info(
            f"{self.lb.module.res_key}.{self.lb.name} - Listener {self.port} found: {self.arn}"
        )

        targets: list[dict] = set_else_none("Targets", self.definition, [])
        if targets and self.lb.services:
            for target in targets:
                target_parts = LISTENER_TARGET_RE.match(target["name"])
                if not target_parts:
                    raise ValueError(
                        f"{self.lb.module.res_key}.{self.lb.name} - Listener {self.port}"
                        f" - Target {target['name']} is not a valid value. Must match",
                        LISTENER_TARGET_RE.pattern,
                    )
                if (
                    f"{target_parts.group('family')}:{target_parts.group('container')}"
                    not in [svc["name"] for svc in self.lb.services]
                ):
                    self.definition["Targets"].remove(target)
        if not self.definition["Targets"]:
            return

    def handle_cognito_pools(self, settings, listener_stack):
        """

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param ecs_composex.common.stacks.ComposeXStack listener_stack:
        :return:
        """
        cognito_auth_key = "AuthenticateCognitoConfig"
        for target in self.services:
            if keyisset("CreateCognitoClient", target):
                user_pool_client_params = target["CreateCognitoClient"]
                pool_id = user_pool_client_params["UserPoolId"]
                pool_params = import_cognito_pool(pool_id, settings, listener_stack)
                user_pool_client_params["UserPoolId"] = pool_params[0]
                user_pool_client_props = import_record_properties(
                    user_pool_client_params, UserPoolClient
                )
                user_pool_client = listener_stack.stack_template.add_resource(
                    UserPoolClient(
                        f"{listener_stack.title}UserPoolClient{NONALPHANUM.sub('', target['name'])}",
                        **user_pool_client_props,
                    )
                )
                if keyisset(cognito_auth_key, target):
                    target[cognito_auth_key]["UserPoolArn"] = pool_params[1]
                    target[cognito_auth_key]["UserPoolDomain"] = pool_params[2]
                    target[cognito_auth_key]["UserPoolClientId"] = Ref(user_pool_client)
                else:
                    LOG.warning(
                        "No AuthenticateCognitoConfig defined. Setting to default settings"
                    )
                    target.update(
                        {
                            cognito_auth_key: {
                                "OnUnauthenticatedRequest": "authenticate",
                                "Scope": "openid email profile",
                                "UserPoolArn": pool_params[1],
                                "UserPoolDomain": pool_params[2],
                                "UserPoolClientId": Ref(user_pool_client),
                            }
                        }
                    )
                del target["CreateCognitoClient"]
            elif (
                not keyisset("CreateCognitoClient", target)
                and keyisset(cognito_auth_key, target)
                and keyisset("UserPoolArn", target[cognito_auth_key])
                and target[cognito_auth_key]["UserPoolArn"].startswith("x-cognito")
            ):
                pool_id = target[cognito_auth_key]["UserPoolArn"].split(r"::")[-1]
                pool_params = import_cognito_pool(pool_id, settings, listener_stack)
                target[cognito_auth_key]["UserPoolArn"] = pool_params[1]
                target[cognito_auth_key]["UserPoolDomain"] = pool_params[2]

    def map_lb_target_groups_service_to_listener_targets(self, lb: Elbv2) -> None:
        """
        Map Services defined in LB definition to Targets
        """
        if not self.services:
            return
        validate_duplicate_targets(lb, self)
        for l_service_def in self.services:
            map_service_target(lb, l_service_def)
            if not keyisset("target_arn", l_service_def):
                raise LookupError(
                    f"{lb.module.res_key}.{lb.name} - Listener {self.arn}",
                    f"Failed to map {l_service_def['name']} to any family:service:port combination",
                )

    def map_target_group_to_listener(self, target_group: MergedTargetGroup) -> None:
        if not self.services:
            LOG.warning(
                f"{self.lb.module.res_key}.{self.lb.name} - Listener {self.Port} - No Targets defined."
            )
            return
        for _tgt_group in self.services:
            _tgt_name = _tgt_group["name"]
            if _tgt_name == target_group.name:
                _tgt_group["target_arn"] = Ref(target_group)
                break
        else:
            LOG.debug(
                f"{self.lb.module.res_key}.{self.lb.name} - Listener {self.Port} - No target group matched."
            )

    def define_new_rules(self, load_balancer, template: Template):
        """
        Method to define new rules

        :param ecs_composex.elbv2.elbv2_stack.Elbv2Stack load_balancer:
        :param troposphere.Template template:
        :return:
        """
        import random

        listener_id = LB_V2_LISTENER_ARN_RE.match(self.arn).group("id")
        last_rule_offset = int(self.rules[-1]["Priority"]) if self.rules else 49999
        starting_offset = last_rule_offset + random.randint(1, 1000)
        offset = starting_offset + random.randint(1, 100)
        rules = []
        for count, service_def in enumerate(self.services):
            priority = offset - count - 1
            rule = ListenerRule(
                f"{NONALPHANUM.sub('', listener_id)}{NONALPHANUM.sub('', service_def['name'])}Rule{count}",
                ListenerArn=self.arn,
                Actions=define_actions(self, service_def, True),
                Priority=priority,
                Conditions=define_target_conditions(service_def),
            )
            rules.append(rule)
        for rule in rules:
            template.add_resource(rule)
