# -*- coding: utf-8 -*-
"""
Main module template to generate the RDS Root template and all stacks according to x-rds settings
"""

from troposphere import Sub, Ref, Join
from troposphere.cloudformation import Stack
from ecs_composex.common import LOG, build_template, validate_kwargs, add_parameters
from ecs_composex.common.tagging import add_object_tags, generate_tags_parameters
from ecs_composex.common.templates import FileArtifact
from ecs_composex.vpc.vpc_params import (
    VPC_ID,
    VPC_ID_T,
    VPC_MAP_ID_T,
    VPC_MAP_ID,
    STORAGE_SUBNETS,
    STORAGE_SUBNETS_T,
)
from ecs_composex.common.cfn_params import ROOT_STACK_NAME_T
from ecs_composex.rds.rds_params import (
    RES_KEY,
    DBS_SUBNET_GROUP,
    DBS_SUBNET_GROUP_T,
    DB_NAME_T,
    DB_INSTANCE_CLASS_T,
    DB_INSTANCE_CLASS,
    DB_ENGINE_VERSION_T,
    DB_ENGINE_VERSION,
    DB_ENGINE_NAME,
    DB_ENGINE_NAME_T,
)
from ecs_composex.rds.rds_db_template import (
    generate_database_template,
    create_db_subnet_group,
)


def add_db_stack(
    root_template, dbs_subnet_group, db_name, db, params_and_tags, **kwargs
):
    """
    Function to add the DB stack to the root stack
    :param dbs_subnet_group: Subnet group for DBs
    :type dbs_subnet_group: troposphere.rds.DBSubnetGroup
    :param root_template: root template to add the nested stack to
    :type root_template: troposphere.Template
    :param db_name: name of the DB as defined in the x-rds section
    :type db_name: str
    :param db: the database definition from the compose file
    :type db: dict
    :param kwargs: extra arguments
    """
    props = db["Properties"]
    required_props = [DB_ENGINE_NAME_T, DB_ENGINE_VERSION_T]
    validate_kwargs(required_props, props)
    non_stack_params = {
        DB_ENGINE_NAME_T: props[DB_ENGINE_NAME_T],
        DB_ENGINE_VERSION_T: props[DB_ENGINE_VERSION_T],
    }
    parameters = {
        VPC_ID_T: Ref(VPC_ID),
        DBS_SUBNET_GROUP_T: Ref(dbs_subnet_group),
        DB_NAME_T: db_name,
        STORAGE_SUBNETS_T: Join(",", Ref(STORAGE_SUBNETS)),
    }
    parameters.update(non_stack_params)
    db_template = generate_database_template(db_name, db, **kwargs)
    if db_template is None:
        return
    if params_and_tags:
        add_parameters(db_template, params_and_tags[0])
        for obj in db_template.resources:
            add_object_tags(db_template.resources[obj], params_and_tags[1])
    db_template_file = FileArtifact(f"{db_name}.yml", template=db_template, **kwargs)
    db_template_file.create()
    Stack(
        db_name,
        template=root_template,
        TemplateURL=db_template_file.url,
        Parameters=parameters,
    )


def generate_rds_templates(compose_content, **kwargs):
    """
    Function to generate the RDS root template for all the DBs defined in the x-rds section of the compose file
    :param compose_content: the docker compose file content
    :type compose_content: dict
    :param kwargs: extra parameters

    :return: rds_root_template, the RDS Root template with nested stacks
    :rtype: troposphere.Template
    """
    rds_root_tpl = build_template("RDS Root template", [VPC_ID, STORAGE_SUBNETS])
    dbs_subnet_group = create_db_subnet_group(rds_root_tpl)
    params_and_tags = generate_tags_parameters(compose_content)
    section = compose_content[RES_KEY]
    for db_name in section:
        add_db_stack(
            rds_root_tpl,
            dbs_subnet_group,
            db_name,
            section[db_name],
            params_and_tags,
            **kwargs,
        )
    if params_and_tags:
        add_parameters(rds_root_tpl, params_and_tags[0])
        for obj in rds_root_tpl.resources:
            add_object_tags(rds_root_tpl.resources[obj], params_and_tags[1])
    return rds_root_tpl
