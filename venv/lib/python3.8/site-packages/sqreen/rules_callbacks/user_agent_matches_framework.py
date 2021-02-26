# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Look for badly behaved clients
"""
from logging import getLogger

from ..rules_actions import RecordAttackMixin
from .regexp_rule import RegexpRule

LOGGER = getLogger(__name__)


class UserAgentMatchesCBFramework(RecordAttackMixin, RegexpRule):

    def pre(self, instance, args, kwargs, options):

        request = self.storage.get_current_request()

        if not request:
            LOGGER.warning("No request was recorded abort")
            return

        user_agent = request.client_user_agent
        if not user_agent:
            return

        match = self.match_regexp(user_agent)
        if not match:
            return

        infos = {"found": match, "in": user_agent}
        self.record_attack(infos)

        return {"status": "raise", "data": match, "rule_name": self.rule_name}


UserAgentMatchesCBDjango = UserAgentMatchesCBFramework
