# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

import logging

from ..ip_radix import Radix
from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin

LOGGER = logging.getLogger(__name__)


class IPBlacklistCB(RecordObservationMixin, RuleCallback):

    INTERRUPTIBLE = False

    def __init__(self, *args, **kwargs):
        super(IPBlacklistCB, self).__init__(*args, **kwargs)
        self.networks = Radix(None)
        for blacklist in self.data.get("values", []):
            self.networks.insert(blacklist, '/' in blacklist)
        LOGGER.debug("Blacklisted IP networks: %s", self.networks)

    def pre(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        if request is None:
            return
        client_ip = request.raw_client_ip
        if client_ip is None:
            return
        network = self.networks.match(client_ip)
        if network is not None:
            LOGGER.debug(
                "IP %s belongs to blacklisted network %s",
                client_ip,
                network,
            )
            self.record_observation("blacklisted", network, 1)
            return {
                "status": "raise",
                "data": network,
                "rule_name": self.rule_name,
                "immediate": True,  # Stop execution of other callbacks on this hook point
            }
