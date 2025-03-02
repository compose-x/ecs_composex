#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2025 John Mille <john@compose-x.io>


# -- CLEANUP FUNCTIONS:
def cleanup_composex_settings(context):
    print("CALLED: cleanup_composex_settings")
    if hasattr(context, "settings"):
        delattr(context.settings, "mod_manager")
    delattr(context, "settings")


# -- HOOKS:
def before_scenario(context, scenario):
    print("CALLED-HOOK: before_scenario:%s" % scenario.name)
    # if "cleanup_context" in scenario.tags:
    #     print("REGISTER-CLEANUP: cleanup_composex_settings")
    #     context.add_cleanup(cleanup_composex_settings, context)


def after_scenario(context, scenario):
    print("CALLED-HOOK: after_scenario:%s" % scenario.name)
    cleanup_composex_settings(context)
