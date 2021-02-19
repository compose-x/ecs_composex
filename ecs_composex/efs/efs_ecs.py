#  -*- coding: utf-8 -*-
#   ECS ComposeX <https://github.com/lambda-my-aws/ecs_composex>
#   Copyright (C) 2020  John Mille <john@lambda-my-aws.io>
#  #
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#  #
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#  #
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


def efs_to_ecs(resources, services_stack, res_root_stack, settings):
    """
    Function to associate back the EFS FS to services.

    :param resources:
    :param services_stack:
    :param res_root_stack:
    :param settings:
    :return:
    """

    efs_mappings = {}
    new_resources = [
        resources[res_name] for res_name in resources if not resources[res_name].lookup
    ]
    lookup_resources = [
        resources[res_name] for res_name in resources if resources[res_name].lookup
    ]
