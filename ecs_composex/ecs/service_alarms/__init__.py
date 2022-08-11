#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>


from copy import deepcopy

from compose_x_common.compose_x_common import keyisset

from ecs_composex.common.logging import LOG

from .service_predefined_alarms import PREDEFINED_SERVICE_ALARMS_DEFINITION


def define_predefined_alarm_settings(family, new_settings):
    """
    Method to define the predefined alarm settings based on the alarm characteristics

    :param new_settings:
    :return:
    """
    for alarm_name, alarm_def in new_settings["Alarms"].items():
        if not keyisset("Properties", alarm_def):
            continue
        props = alarm_def["Properties"]
        if not keyisset("MetricName", props):
            raise KeyError("You must define a MetricName for the pre-defined alarm")
        metric_name = props["MetricName"]
        if metric_name == "RunningTaskCount":
            range_key = "max"
            if keyisset("range_key", new_settings):
                range_key = new_settings["range_key"]
            new_settings["Settings"][
                metric_name
            ] = family.service_scaling.scaling_range[range_key]


def define_predefined_alarms(family):
    """
    Method to define which predefined alarms are available
    :return: dict of the alarms
    :rtype: dict
    """

    finalized_alarms = {}
    for name, settings in PREDEFINED_SERVICE_ALARMS_DEFINITION.items():
        if (
            keyisset("requires_scaling", settings)
            and not family.service_scaling.defined
        ):
            LOG.debug(
                f"{family.name} - No x-scaling.Range defined for the service and rule {name} requires it. Skipping"
            )
            continue
        new_settings = deepcopy(settings)
        define_predefined_alarm_settings(family, new_settings)
        finalized_alarms[name] = new_settings
    return finalized_alarms


def validate_service_predefined_alarms(family, valid_predefined, service_predefined):
    """
    Validates that the alarms set to use exist

    :raises: KeyError if the name for Predefined alarm is not found in services alarms
    """
    if not all(name in valid_predefined.keys() for name in service_predefined.keys()):
        raise KeyError(
            f"For {family.logical_name}, only valid service_predefined alarms are",
            valid_predefined.keys(),
            "Got",
            service_predefined.keys(),
        )


def define_default_alarm_settings(family, key, value, settings_key, valid_predefined):
    if not keyisset(key, family.predefined_alarms):
        family.predefined_alarms[key] = valid_predefined[key]
        family.predefined_alarms[key][settings_key] = valid_predefined[key][
            settings_key
        ]
        if isinstance(value, dict) and keyisset(settings_key, value):
            family.predefined_alarms[key][settings_key] = valid_predefined[key][
                settings_key
            ]
            for subkey, subvalue in value[settings_key].items():
                family.predefined_alarms[key][settings_key][subkey] = subvalue


def merge_alarm_settings(family, key, value, settings_key, valid_predefined):
    """
    Method to merge multiple services alarms definitions

    :param str key:
    :param dict value:
    :param str settings_key:
    :return:
    """
    for subkey, subvalue in value[settings_key].items():
        if isinstance(subvalue, (int, float)) and keyisset(
            subkey, family.predefined_alarms[key][settings_key]
        ):
            set_value = family.predefined_alarms[key][settings_key][subkey]
            new_value = subvalue
            LOG.warning(
                f"{family.name} - Value for {key}.Settings.{subkey} override from {set_value} to {new_value}."
            )
            family.predefined_alarms[key]["Settings"][subkey] = new_value


def set_merge_alarm_topics(family, key, value):
    topics = value["Topics"]
    set_topics = []
    if keyisset("Topics", family.predefined_alarms[key]):
        set_topics = family.predefined_alarms[key]["Topics"]
    else:
        family.predefined_alarms[key]["Topics"] = set_topics
    for topic in topics:
        if isinstance(topic, str) and topic not in [
            t for t in set_topics if isinstance(t, str)
        ]:
            set_topics.append(topic)
        elif (
            isinstance(topic, dict)
            and keyisset("x-sns", topic)
            and topic["x-sns"]
            not in [
                t["x-sns"]
                for t in set_topics
                if isinstance(t, dict) and keyisset("x-sns", t)
            ]
        ):
            set_topics.append(topic)


def assign_predefined_alerts(
    family, service_predefined, valid_predefined, settings_key
):
    for key, value in service_predefined.items():
        if not keyisset(key, family.predefined_alarms):
            define_default_alarm_settings(
                family, key, value, settings_key, valid_predefined
            )
        elif (
            keyisset(key, family.predefined_alarms)
            and isinstance(value, dict)
            and keyisset(settings_key, value)
        ):
            merge_alarm_settings(family, key, value, settings_key, valid_predefined)
        if keyisset("Topics", value):
            set_merge_alarm_topics(family, key, value)


def handle_alarms(family):
    """
    Method to define the alarms for the services.
    """
    valid_predefined = define_predefined_alarms(family)
    LOG.debug(family.logical_name, valid_predefined)
    if not valid_predefined:
        return
    alarm_key = "x-alarms"
    settings_key = "Settings"
    for service in family.services:
        if keyisset(alarm_key, service.definition) and keyisset(
            "Predefined", service.definition[alarm_key]
        ):
            service_predefined = service.definition[alarm_key]["Predefined"]
            validate_service_predefined_alarms(
                family, valid_predefined, service_predefined
            )
            assign_predefined_alerts(
                family, service_predefined, valid_predefined, settings_key
            )
            LOG.debug(family.predefined_alarms)
