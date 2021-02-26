# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record observations
"""
import logging

from ..utils import datetime_from_isoformat, is_unicode, naive_dt_to_utc, now

LOGGER = logging.getLogger(__name__)


class RecordObservationMixin(object):

    def action_processor(self, result_action, options):
        result_action = super(RecordObservationMixin, self).action_processor(result_action, options)
        if result_action is None:
            return
        observations = result_action.get("observations")
        if observations is not None:
            for observation in observations:
                observation = list(observation)
                if len(observation) > 3:
                    at = observation[3]
                    if is_unicode(at):
                        at = datetime_from_isoformat(at)
                    observation[3] = naive_dt_to_utc(at)
                else:
                    observation.append(options.get("at"))
                self.record_observation(*observation)
        return result_action

    def record_observation(self, metric_name, key, value, at=None):
        """Record a metric observation."""
        if at is None:
            at = now()
        payload = (metric_name, at, key, value)
        LOGGER.debug("Observed metric %r", payload)
        self.storage.observe("observations", payload, report=False)
