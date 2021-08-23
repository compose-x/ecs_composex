﻿#  -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2021 John Mille <john@compose-x.io>

"""
AWS DocumentDB entrypoint for ECS ComposeX
"""

from compose_x_common.compose_x_common import keyisset
from troposphere import GetAtt, Ref

from ecs_composex.common.compose_resources import (
    XResource,
    set_lookup_resources,
    set_new_resources,
    set_resources,
    set_use_resources,
)
from ecs_composex.common.stacks import ComposeXStack
from ecs_composex.docdb.docdb_ecs import create_lookup_mappings
from ecs_composex.docdb.docdb_params import (
    DOCDB_NAME,
    DOCDB_PORT,
    DOCDB_SECRET,
    DOCDB_SG,
    MAPPINGS_KEY,
    MOD_KEY,
    RES_KEY,
)
from ecs_composex.docdb.docdb_template import (
    create_docdb_template,
    init_doc_db_template,
)
from ecs_composex.vpc.vpc_params import STORAGE_SUBNETS


class DocDb(XResource):
    """
    Class to manage DocDB
    """

    subnets_param = STORAGE_SUBNETS

    def __init__(self, name, definition, module_name, settings, mapping_key=None):
        """
        Init method

        :param str name:
        :param dict definition:
        :param ecs_composex.common.settings.ComposeXSettings settings:
        """
        self.db_secret = None
        self.db_sg = None
        self.db_subnets_group = None
        super().__init__(
            name, definition, module_name, settings, mapping_key=mapping_key
        )
        self.set_override_subnets()

    def init_outputs(self):
        """
        Method to init the DocDB output attributes
        """
        self.output_properties = {
            DOCDB_NAME: (self.logical_name, self.cfn_resource, Ref, None),
            DOCDB_PORT: (
                f"{self.logical_name}{DOCDB_PORT.return_value}",
                self.cfn_resource,
                GetAtt,
                DOCDB_PORT.return_value,
            ),
            DOCDB_SECRET: (
                self.db_secret.title,
                self.db_secret,
                Ref,
                None,
            ),
            DOCDB_SG: (
                self.db_sg.title,
                self.db_sg,
                GetAtt,
                DOCDB_SG.return_value,
            ),
        }


class XStack(ComposeXStack):
    """
    Class for the Stack of DocDB
    """

    def __init__(self, title, settings, **kwargs):
        set_resources(settings, DocDb, RES_KEY, MOD_KEY, mapping_key=MAPPINGS_KEY)
        x_resources = settings.compose_content[RES_KEY].values()
        new_resources = set_new_resources(x_resources, RES_KEY, True)
        lookup_resources = set_lookup_resources(x_resources, RES_KEY)
        use_resources = set_use_resources(x_resources, RES_KEY, False)
        if new_resources:
            stack_template = init_doc_db_template()
            super().__init__(title, stack_template, **kwargs)
            create_docdb_template(stack_template, new_resources, settings, self)
        else:
            self.is_void = True
        if lookup_resources or use_resources:
            if not keyisset(RES_KEY, settings.mappings):
                settings.mappings[RES_KEY] = {}
            create_lookup_mappings(
                settings.mappings[RES_KEY], lookup_resources, settings
            )
        for resource in settings.compose_content[RES_KEY].values():
            resource.stack = self
