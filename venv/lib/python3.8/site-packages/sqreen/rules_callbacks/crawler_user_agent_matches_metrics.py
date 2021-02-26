# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Look for known crawlers user-agents
"""

from logging import getLogger

from ..rules_actions import RecordObservationMixin
from .matcher_callback import MatcherRule

LOGGER = getLogger(__name__)


class CrawlerUserAgentMatchesMetricsCB(RecordObservationMixin, MatcherRule):
    def pre(self, instance, args, kwargs, options):
        """ For each request, record an observation with the user_agent without
        case modification.
        """
        request = self.storage.get_current_request()

        if not request:
            LOGGER.warning("No request was recorded abort")
            return

        user_agent = request.client_user_agent

        if not user_agent:
            return

        if self.match(user_agent):
            self.record_observation("crawler", user_agent, 1)
