#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

import warnings
from copy import deepcopy

from compose_x_common.compose_x_common import keyisset
from troposphere import Ref
from troposphere.cognito import UserPoolClient
from troposphere.elasticloadbalancingv2 import Listener

import ecs_composex.common.troposphere_tools
from ecs_composex.common import NONALPHANUM
from ecs_composex.common.logging import LOG
from ecs_composex.elbv2.elbv2_stack.helpers import (
    add_acm_certs_arn,
    define_actions,
    handle_default_actions,
    handle_non_default_services,
    import_cognito_pool,
    import_new_acm_certs,
    map_service_target,
)
from ecs_composex.resources_import import import_record_properties


class ComposeListener(Listener):
    attributes = [
        "Condition",
        "CreationPolicy",
        "DeletionPolicy",
        "DependsOn",
        "Metadata",
        "UpdatePolicy",
        "UpdateReplacePolicy",
    ]

    targets_keys = "Targets"

    def __init__(self, lb, definition):
        """
        Method to init listener.

        :param ecs_composex.elbv2.elbv2_stack.elbv2.Elbv2 lb:
        :param dict definition:
        """
        self.definition = deepcopy(definition)
        straight_import_keys = ["Port", "Protocol", "SslPolicy", "AlpnPolicy"]
        listener_kwargs = {
            x: self.definition[x] for x in straight_import_keys if x in self.definition
        }
        listener_kwargs.update(
            {x: self.definition[x] for x in self.attributes if x in self.definition}
        )
        self.services = (
            self.definition[self.targets_keys]
            if keyisset(self.targets_keys, self.definition)
            and isinstance(self.definition[self.targets_keys], list)
            else []
        )
        self.default_actions = (
            self.definition["DefaultActions"]
            if keyisset("DefaultActions", self.definition)
            else []
        )
        listener_kwargs.update({"LoadBalancerArn": Ref(lb.lb)})
        self.name = f"{lb.logical_name}{listener_kwargs['Port']}"
        super().__init__(self.name, **listener_kwargs)
        self.DefaultActions = []

    def define_default_actions(self, template):
        """
        If DefaultTarget is set it will set it if not a service, otherwise at the service level.
        If not defined, and there is more than one service, it will fail.
        If not defined and there is only one service defined, it will skip
        """
        if not self.default_actions and not self.services:
            warnings.warn(
                f"{self.name} - There are no actions defined or services for listener {self.title}. Skipping"
            )
            return
        if self.default_actions:
            handle_default_actions(self)
        elif not self.default_actions and self.services and len(self.services) == 1:
            LOG.info(
                f"{self.title} has no defined DefaultActions and only 1 service. Default all to service."
            )
            self.DefaultActions = define_actions(self, self.services[0])
        elif not self.default_actions and self.services and len(self.services) > 1:
            LOG.warning(
                f"{self.title} - "
                "No default actions defined and more than one service defined. "
                "If one of the access path is / it will be used as default"
            )
            rules = handle_non_default_services(self, self.services)
            for rule in rules:
                template.add_resource(rule)
        else:
            raise ValueError(f"Failed to determine any default action for {self.title}")

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

    def handle_certificates(self, settings, listener_stack):
        """
        Method to handle certificates

        :param ecs_composex.common.settings.ComposeXSettings settings:
        :param listener_stack: The stack that has the listener as resource

        :return:
        """
        if not keyisset("Certificates", self.definition):
            LOG.warning(f"No certificates defined for Listener {self.name}")
            return
        valid_sources = [
            ("x-acm", str, import_new_acm_certs),
            ("Arn", str, add_acm_certs_arn),
            ("CertificateArn", str, add_acm_certs_arn),
        ]
        for cert_def in self.definition["Certificates"]:
            if isinstance(cert_def, dict):
                cert_source = list(cert_def.keys())[0]
                source_value = cert_def[cert_source]
                for src_type in valid_sources:
                    if (
                        src_type[0] == cert_source
                        and isinstance(cert_source, src_type[1])
                        and src_type[2]
                    ):
                        src_type[2](self, source_value, settings, listener_stack)

    def validate_mapping(self, lb, t_targets, l_targets):
        """
        Method to validate the services mapping

        :param ecs_composex.elbv2.elbv2_stack.elbv2.Elbv2 lb:
        :param list t_targets:
        :param list l_targets:
        :return:
        """
        if not all(target in t_targets for target in l_targets):
            raise KeyError(
                "Missing one of ",
                [
                    i
                    for i in l_targets + t_targets
                    if i not in l_targets or i not in t_targets
                ],
                f" in {lb.logical_name} Services for listener {self.title}",
            )

    def map_lb_services_to_listener_targets(self, lb):
        """
        Map Services defined in LB definition to Targets

        :param ecs_composex.elbv2.elbv2_stack.elbv2.Elbv2 lb:
        """
        if not self.services:
            return
        l_targets = [s["name"] for s in self.services]
        t_targets = [s["name"] for s in lb.services]
        self.validate_mapping(lb, t_targets, l_targets)
        for l_service_def in self.services:
            name = l_service_def["name"]
            map_service_target(lb, name, l_service_def)
