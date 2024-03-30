#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2020-2022 John Mille <john@compose-x.io>

"""
Root stack to store and manage the security groups of the services
Having the security groups created before the services stacks allows to define service to service communication
to be defined before the services are deployed.
"""
