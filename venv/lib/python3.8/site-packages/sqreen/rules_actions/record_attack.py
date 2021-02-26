# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record observations
"""
import logging

from ..utils import now

LOGGER = logging.getLogger(__name__)


class RecordAttackMixin(object):
    """
    Mixin for rule callbacks to record attacks.
    """

    DEFAULT_ATTACK_SECTIONS = ("request", "response", "params", "headers", "context")

    def action_processor(self, result_action, options):
        """
        Record attacks from the callback return value.
        """
        result_action = super(RecordAttackMixin, self).action_processor(result_action, options)
        if result_action is None:
            return
        record = result_action.get("record")
        if record:
            self.record_attack(infos=record, at=options.get("at"))
        return result_action

    def record_attack(self, infos=None, at=None):
        """Record an attack."""
        if at is None:
            at = now()
        payload = {
            "infos": infos,
            "rulespack_id": self.rulespack_id,
            "rule_name": self.rule_name,
            "beta": self.beta,
            "block": self.block,
            "test": self.test,
            "attack_type": self.attack_type,
            "time": at,
        }
        payload_sections = self.payload_sections
        if payload_sections is None:
            payload_sections = self.DEFAULT_ATTACK_SECTIONS
        if "context" in payload_sections:
            current_request = self.storage.get_current_request()
            if current_request:
                payload["backtrace"] = list(current_request.raw_caller)
        LOGGER.debug("Observed attack %r", payload)
        self.storage.observe("attacks", payload, payload_sections=payload_sections, report=True)
