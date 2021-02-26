# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import itertools
import logging

from ..rules import ReactiveRuleCallback
from .waf import WAFCBMixin

LOGGER = logging.getLogger(__name__)


class ReactiveWAF(WAFCBMixin, ReactiveRuleCallback):
    """ WAF Callback
    """

    def __init__(self, *args, **kwargs):
        super(ReactiveWAF, self).__init__(*args, **kwargs)

        values = self.data.get("values", {})
        self.batch_addresses = frozenset(itertools.chain.from_iterable(
            values.get("rule_request", [])))

    def handler(self, instance, args, kwargs, options):
        budget = self.get_remaining_budget(options)
        if budget is None:
            budget = self.max_budget_ms

        waf_context = self.storage.get_request_store().get(self.waf_rules_id)
        if waf_context is None:
            LOGGER.debug("create a new WAF context for request")
            waf_context = self._inst.create_context()
            self.storage.update_request_store(**{self.waf_rules_id: waf_context})

        return self.execute(waf_context, dict(args[0]), budget)
