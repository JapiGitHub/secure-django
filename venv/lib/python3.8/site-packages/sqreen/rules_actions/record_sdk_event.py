# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record SDK events
"""
import logging

from ..utils import now

LOGGER = logging.getLogger(__name__)


class RecordSDKEventMixin(object):
    """
    Mixin for rule callbacks to record SDK Events.
    """

    DEFAULT_SDK_EVENT_SECTIONS = ("request", "response", "headers", "local")

    source = "track"

    def action_processor(self, result_action, options):
        """
        Record SDK events from the callback return value.
        """
        result_action = super(RecordSDKEventMixin, self).action_processor(result_action, options)
        if result_action is None:
            return
        records = result_action.get("sdk")
        if records:
            for record, record_options in records:
                if record_options.get("timestamp") is None:
                    record_options["timestamp"] = options.get("at")
                self.record_sdk_event(record, record_options)
        return result_action

    def record_sdk_event(self, event, options):
        """Track an SDK event.

        This function is used internally in the agent to send built-in SDK events,
        e.g. output of security actions. It does not perform any check and is not
        exposed to the user.
        """
        if options.get("timestamp") is None:
            options["timestamp"] = now()
        payload_sections = self.payload_sections
        if payload_sections is None:
            payload_sections = self.DEFAULT_SDK_EVENT_SECTIONS
        payload_sections = set(payload_sections)
        if options.get("collect_body", False):
            payload_sections.add("params")
        self.storage.observe(
            "sdk",
            [self.source, options["timestamp"], event, options],
            payload_sections=payload_sections,
            report=True,
        )
