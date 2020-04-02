# -*- coding: utf-8 -*-
"""
From the docker ComposeX definition file, allows to add generic tags to all objects supporting AWS Tags from CFN

Obviously as per AWS CFN API, when you create a stack with Tags, these tags propagate to all resources that support
tagging via CFN. Which is great, but very little people use that. And given that the AWS Stack itself has no cost,
the FinOps people usually only are able to track the resources that generate actual billing.

By adding the tags to the resources wherever supported and have these as parameters, this enforces the presence of some
tags, even though their values might differ. Using parameters to set the values also allows to copy-paste templates
within the same organization and simply change the values at the time of creating the CFN Stack.

You might have IAM policies in place to try to force tagging. I find this doesn't use a lot of parameters unless you had
an insane number of tags.

When defining the tags in ComposeX as a list, the names of your tags can contain some special characters which
otherwise you could not, i.e., *vpc::usage::ecsapps*

"""

import copy

from troposphere import Tags, Parameter, Ref

from ecs_composex.common import KEYISSET, NONALPHANUM, LOG


def define_tag_parameter_title(tag_name):
    """
    Returns the formatted name title for a given tag

    :param tag_name: name of the tag as defined in the ComposeX file
    :type tag_name: str
    :return: reformatted tag name to work on CFN
    :rtype: str
    """
    return f"{NONALPHANUM.sub('', tag_name).strip().title()}Tag"


def define_extended_tags(tags):
    """
    Function to generate the tags to be added to objects from x-tags

    :param tags: tags as defined in composex file
    :type tags: list or dict
    :return: Tags() or None
    :rtype: troposphere.Tags or None
    """
    tags_keys = ['name', 'value']
    rendered_tags = []
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                raise TypeError('Tags must be of type', dict)
            elif not set(tag.keys()) == set(tags_keys):
                raise KeyError('Keys for tags must be', 'value', 'name')
            rendered_tags.append({
                tag['name']: Ref(define_tag_parameter_title(tag['name']))
            }
            )
    elif isinstance(tags, dict):
        for tag in tags:
            rendered_tags.append({tag: Ref(define_tag_parameter_title(tag))})
    if tags:
        return Tags(*rendered_tags)
    return None


def generate_tags_parameters(composex_content):
    """
    Function to generate a list of parameters used for the tags values

    :param composex_content: docker composeX file content
    :type composex_content: dict
    :return: list of parameters and tags to add to objects
    :rtype: tuple
    """
    if not KEYISSET('x-tags', composex_content):
        LOG.info('No x-tags found. Skipping')
        return
    xtags = composex_content['x-tags']
    object_tags = define_extended_tags(xtags)
    parameters = []
    for tag in xtags:
        parameters.append(
            Parameter(
                define_tag_parameter_title(tag['name']) if isinstance(xtags, list) else define_tag_parameter_title(tag),
                Type='String',
                MinLength=2,
                MaxLength=128,
                AllowedPattern=r'[\x20-\x7E]+',
                ConstraintDescription="Must be ASCII",
                Default=tag['value'] if isinstance(xtags, list) else xtags[tag]
            )
        )
    return parameters, object_tags


def add_object_tags(obj, tags):
    """
    Function to add tags to the object if the object supports it

    :param obj: Troposphere object to add the tags to
    :param tags: list of tags as defined in Docker composeX file
    :type tags: dict or list
    """
    clean_tags = copy.deepcopy(tags)
    if hasattr(obj, 'props') and 'Tags' not in obj.props:
        return
    if hasattr(obj, 'Tags') and isinstance(getattr(obj, 'Tags'), Tags):
        LOG.debug(f'Adding the new tags {clean_tags} to {obj}')
        existing_tags = getattr(obj, 'Tags')
        new_tags = existing_tags + clean_tags
        setattr(obj, 'Tags', new_tags)
    elif not hasattr(obj, 'Tags'):
        LOG.debug(f'Adding tags to {obj}')
        setattr(obj, 'Tags', tags)
