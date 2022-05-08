# SPDX-License-Identifier: MPL-2.0
# Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Module to import CFN Resources defined by their properties
"""

from __future__ import annotations

from inspect import isfunction

from compose_x_common.compose_x_common import keyisset, keypresent
from troposphere import AWSHelperFn, AWSObject, AWSProperty


def skip_if(resource, prop_attr) -> bool:
    """
    Helper function to skip when conditions are not met to link one resource to another.
    :param resource:
    :param prop_attr:
    :return:
    """
    if not prop_attr:
        return True
    prop_attr_value = getattr(prop_attr[0], prop_attr[1])
    if not isinstance(prop_attr_value, str):
        return True
    if not prop_attr_value.startswith(resource.module.res_key):
        return True
    if resource.name not in prop_attr_value.split(resource.module.res_key)[-1]:
        return True
    return False


def get_dest_resource_nested_property(
    properties_path: str, dest_resource: AWSObject | AWSProperty
) -> tuple | None:
    """
    Function that will return the
    :param properties_path:
    :param dest_resource:
    :return:
    """
    parts = properties_path.split(r"::", 1)
    if not hasattr(dest_resource, parts[0]):
        return None
    if parts[0] != parts[-1]:
        return get_dest_resource_nested_property(
            parts[-1], getattr(dest_resource, parts[0])
        )
    return dest_resource, parts[-1]


def handle_list(properties, property_class):
    """
    Function to handle list properties

    :param property_class:
    :param properties:
    :return:
    """
    rendered_properties = []
    for property_definition in properties:
        if not isinstance(property_definition, (str, int, float, bool)):
            record = import_record_properties(property_definition, property_class)
            rendered_properties.append(property_class(**record))
        else:
            rendered_properties.append(property_definition)
    return rendered_properties


def import_non_functions(
    props, prop_name, top_class, properties, set_to_novalue, ignore_missing
):
    """
    Function to set property for flat object or recursive to sub properties

    :param dict props:
    :param str prop_name:
    :param top_class:
    :param dict properties:
    :param bool set_to_novalue:
    :param bool ignore_missing:
    """
    if isinstance(properties[prop_name], AWSHelperFn):
        props[prop_name] = properties[prop_name]
    elif isinstance(properties[prop_name], (str, int, float, tuple)) or top_class.props[
        prop_name
    ][0] in (
        str,
        int,
        float,
    ):
        if top_class.props[prop_name][0] in (str, int, float):
            props[prop_name] = top_class.props[prop_name][0](properties[prop_name])
        else:
            props[prop_name] = properties[prop_name]
    elif isinstance(properties[prop_name], dict):
        try:
            if issubclass(top_class.props[prop_name][0], AWSProperty):
                sub_props = import_record_properties(
                    properties[prop_name],
                    top_class.props[prop_name][0],
                    set_to_novalue,
                    ignore_missing_required=ignore_missing,
                )
                props[prop_name] = top_class.props[prop_name][0](**sub_props)
            else:
                props[prop_name] = properties[prop_name]
        except TypeError:
            props[prop_name] = properties[prop_name]


def import_record_properties(
    properties,
    top_class,
    set_to_novalue=False,
    ignore_missing_required=True,
    ignore_missing_sub_required=False,
):
    """
    Generic function importing the RecordSet properties.
    If the property was not defined, it is either left empty or set to AWS::NoValue
    For inner recursive, we enforce check on required properties.

    :param dict properties:
    :param top_class: The class we are going to import properties for
    :param bool set_to_novalue: Instead of skipping the property, actively set to AWS::NoValue
    :param bool ignore_missing_required: Whether raise an error when missing an essential key.
    :param bool ignore_missing_sub_required: Whether raise an error when missing an essential key in sub properties
    :return:  The properties for the RecordSet
    :rtype: dict
    """
    props = {}
    for prop_name in top_class.props:
        if not keypresent(prop_name, properties) and not top_class.props[prop_name][1]:
            continue
        elif (
            not keypresent(prop_name, properties)
            and top_class.props[prop_name][1]
            and not ignore_missing_required
        ):
            raise KeyError(
                f"Property {prop_name} is required for the definition of {top_class}"
            )
        elif keyisset(prop_name, properties) and isinstance(
            top_class.props[prop_name][0], list
        ):
            props[prop_name] = handle_list(
                properties[prop_name], top_class.props[prop_name][0][0]
            )
        elif keypresent(prop_name, properties) and isfunction(
            top_class.props[prop_name][0]
        ):
            props[prop_name] = properties[prop_name]
        elif keypresent(prop_name, properties) and not isfunction(
            properties[prop_name]
        ):
            import_non_functions(
                props,
                prop_name,
                top_class,
                properties,
                set_to_novalue,
                ignore_missing_sub_required,
            )
        elif keypresent(prop_name, properties):
            props[prop_name] = properties[prop_name]
    return props


def find_aws_resources_in_template_resources(root_stack, resource_types) -> list:
    """
    Function looking for resources in the stack template that are of the type we are looking for.

    :param ComposeXStack root_stack:
    :param tuple(AWSObject) resource_types: the AWSObject resources types we are looking for.
    :return: List of resources of the given type
    :rtype: list
    """
    resources = []
    if not root_stack or not hasattr(root_stack, "stack_template"):
        return resources
    for r_name, resource in root_stack.stack_template.resources.items():
        if not issubclass(type(resource), AWSObject):
            continue
        if issubclass(type(resource), AWSObject) and isinstance(
            resource, resource_types
        ):
            resources.append(resource)
    return resources


def find_aws_properties_in_aws_resource(
    property_type_to_find, resource_properties, found_properties=None
) -> list:
    """

    :param property_type_to_find:
    :param dict resource_properties:
    :param list found_properties:
    :return:
    """
    if isinstance(resource_properties, AWSObject):
        return find_aws_properties_in_aws_resource(
            property_type_to_find, resource_properties.properties
        )
    if found_properties is None:
        found_properties = []
    if isinstance(resource_properties, property_type_to_find):
        found_properties.append(resource_properties)
    elif isinstance(resource_properties, dict):
        for r_property in resource_properties.values():
            if isinstance(r_property, property_type_to_find):
                found_properties.append(r_property)
            elif isinstance(r_property, list):
                for sub_property in r_property:
                    find_aws_properties_in_aws_resource(
                        property_type_to_find, sub_property, found_properties
                    )

            elif issubclass(type(r_property), AWSProperty):
                find_aws_properties_in_aws_resource(
                    property_type_to_find, r_property.properties
                )
    return found_properties
