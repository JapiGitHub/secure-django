# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Record Transport signals
"""
import logging

from .._vendors.sqreen_security_signal_sdk import Signal, SignalType
from ..runtime_infos import get_agent_type
from ..utils import now

LOGGER = logging.getLogger(__name__)


class RecordSignalMixin(object):

    DEFAULT_SIGNAL_SECTIONS = ("request", "local")

    def action_processor(self, result_action, options):
        result_action = super(RecordSignalMixin, self).action_processor(result_action, options)
        if result_action is None:
            return
        standalone_points = result_action.get("standalone_points")
        if standalone_points:
            for signal in standalone_points:
                decision = options.get("sampling_decisions", {}).get(self.rule_name)
                self.record_signal(
                    signal_name=signal.get("signal_name"),
                    payload=signal.get("payload"),
                    payload_schema=signal.get("payload_schema"),
                    trigger=decision.attrs["trigger"] if decision else None,
                    at=options.get("at"),
                    ignore_trace=True,
                )
        signals = result_action.get("signals")
        if signals:
            for signal in signals:
                decision = options.get("sampling_decisions", {}).get(self.rule_name)
                self.record_signal(
                    signal_name=signal.get("signal_name"),
                    payload=signal.get("payload"),
                    payload_schema=signal.get("payload_schema"),
                    trigger=decision.attrs["trigger"] if decision else None,
                    at=options.get("at"),
                )
        return result_action

    def record_signal(self, signal_name, payload, payload_schema, trigger=None, at=None,
                      ignore_trace=False):
        use_signals = self.runner.session.use_signals
        if not use_signals:
            return False
        if at is None:
            at = now()
        signal = Signal(
            type=SignalType.POINT,
            signal_name=signal_name,
            payload_schema=payload_schema,
            payload=payload,
            source="sqreen:agent:{}".format(get_agent_type()),
            time=at,
        )
        if trigger is not None:
            signal["trigger"] = trigger
        if not ignore_trace and self.storage.get_current_request():
            LOGGER.debug("Observed signal %r: %r", signal_name, signal)
            payload_sections = self.payload_sections
            if payload_sections is None:
                payload_sections = self.DEFAULT_SIGNAL_SECTIONS
            self.storage.observe("signals", signal, payload_sections=payload_sections, report=True)
        else:
            self.runner.queue.put(signal)
        return True
