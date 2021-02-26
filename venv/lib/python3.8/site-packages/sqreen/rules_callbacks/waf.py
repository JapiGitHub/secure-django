# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import hashlib
import json
import logging
from threading import Lock
from weakref import WeakKeyDictionary

from ..binding_accessor import BindingAccessor
from ..exceptions import InvalidArgument, SqreenException
from ..rules import RuleCallback
from ..rules_actions import RecordAttackMixin, RecordObservationMixin
from ..runner import BaseRunner
from ..runtime_infos import get_agent_type
from ..samplers import ScopedTracingSampler
from ..utils import HAS_TYPING, is_unicode

if HAS_TYPING:
    from typing import Mapping, MutableMapping
else:
    from collections import Mapping

try:
    from sq_native import input as waf_input, waf  # type: ignore
except Exception:
    waf = None  # pragma: no cover


LOGGER = logging.getLogger(__name__)


class WAFException(SqreenException):

    def __init__(self, msg, waf_rules_id, ret, arguments):
        super(WAFException, self).__init__(msg)
        self.waf_rules_id = waf_rules_id
        self.ret = ret
        self.arguments = arguments

    def exception_infos(self):
        data = self.ret.data
        if data is not None and isinstance(data, bytes):
            data = data.decode("utf-8")
        return {
            "args": [],
            "waf": {
                "args": self.arguments,
                "waf_rule": self.waf_rules_id,
                "error_code": self.ret.action,
                "error_data": data,
            }
        }


class WAFInstances:

    class DummyRunner(BaseRunner):
        pass

    _pool = WeakKeyDictionary()  # type: MutableMapping[BaseRunner, waf.WAFEngine]
    _lock = Lock()
    _dummy_runner = DummyRunner()

    @classmethod
    def get_for_runner(cls, waf_rules_id, waf_rules, runner=None):
        """ Get the WAF instance associated with the runner.
        """
        if runner is None:
            runner = cls._dummy_runner

        with cls._lock:
            instances = cls._pool.get(runner)
            if instances is None:
                instances = cls._pool[runner] = {}
            instance = instances.get(waf_rules_id)
            if instance is None or instance._waf_rules_id != waf_rules_id:
                LOGGER.debug("Instanciate new WAF engine for %s", waf_rules_id)
                instance = instances[waf_rules_id] = waf.WAFEngine(waf_rules)
                instance._waf_rules_id = waf_rules_id
            return instance


class WAFCBMixin(RecordAttackMixin, RecordObservationMixin):

    SUPPORTS_BUDGET = True

    DEFAULT_MAX_BUDGET_MS = 5
    DEFAULT_MAX_INPUT_DEPTH = 10
    DEFAULT_MAX_STRING_LENGTH = 4096
    DEFAULT_MAX_INPUT_ITEMS = 150
    DEFAULT_METRICS_SAMPLING = {
        "enabled": True,
        "sampling": [{"random": 0.01}]
    }

    def __init__(self, *args, **kwargs):
        super(WAFCBMixin, self).__init__(*args, **kwargs)
        if not self.module_is_available():
            msg = "WAF is disabled because the native module is not installed"
            raise InvalidArgument(msg)

        values = self.data.get("values", {})
        waf_rules = values.get("waf_rules")

        if is_unicode(waf_rules):
            waf_rules = waf_rules.encode("utf-8", errors="surrogatepass")
        if not isinstance(waf_rules, bytes):
            raise InvalidArgument("Invalid WAF rules")

        waf_rules_hash = hashlib.sha256(waf_rules).hexdigest()
        self.waf_rules_id = "{}_{}".format(waf_rules_hash, self.rule_name)

        self._inst = WAFInstances.get_for_runner(self.waf_rules_id, waf_rules, self.runner)

        self.max_budget_ms = values.get("max_budget_ms", self.DEFAULT_MAX_BUDGET_MS)
        self.max_input_depth = values.get("max_input_depth", self.DEFAULT_MAX_INPUT_DEPTH)
        self.max_string_length = values.get("max_string_length", self.DEFAULT_MAX_STRING_LENGTH)
        self.max_input_items = values.get("max_input_items", self.DEFAULT_MAX_INPUT_ITEMS)

        metrics_sampling_definition = values.get("metrics_sampling", self.data.get("metrics_sampling", self.DEFAULT_METRICS_SAMPLING))
        self.metrics_sampling = ScopedTracingSampler(metrics_sampling_definition)

    def execute(self, waf_context, params, budget):
        LOGGER.debug("WAF parameters: %r", params)
        with self.storage.trace() as trace:
            pw_params = waf_input.Input.from_python(
                params, max_depth=self.max_input_depth,
                max_string_length=self.max_string_length,
                max_items=self.max_input_items)

        budget -= trace.duration_ms
        if budget <= 0:
            LOGGER.debug("skipping WAF because params convertion is overtime")
            return

        ret = waf_context.run(pw_params, int(min(budget, self.max_budget_ms) * 1000))
        LOGGER.debug("WAF returned: %r", ret)

        self.record_observation("sq.internal.powerwaf.full", None, ret.perf_total_runtime / 1000.0, at=trace.start_at)
        if ret.perf_cache_hit_rate:
            self.record_observation("cache.internal.powerwaf.resolved", None, ret.perf_cache_hit_rate, at=trace.start_at)
        if ret.perf_data:
            # Record detailled metrics only if the request is sampled
            request = self.storage.get_current_request()
            random_value = request.request_rate if request is not None else None
            if self.metrics_sampling.should_sample(random_value=random_value):
                perf_data = json.loads(ret.perf_data.decode("utf-8", errors="replace"))
                for name, value in perf_data.get("topRuleRuntime"):
                    self.record_observation("sq.internal.powerwaf.{}".format(name), None, value / 1000.0, at=trace.start_at)

        if ret.report:
            waf_data = json.loads(ret.data.decode("utf-8", errors="replace"))
            self.record_waf_attack(waf_data, at=trace.start_at)
            if ret.block and self.block is True:
                return {"status": "raise", "rule_name": self.rule_name}
        elif ret.error and not ret.timeout:
            raise WAFException(
                "WAF returned unexpected action", self.waf_rules_id, ret, params)

    def record_waf_attack(self, waf_data, **kwargs):
        """ Record a WAF attack.
        """
        self.record_attack(infos={"waf_data": waf_data}, **kwargs)

    @staticmethod
    def module_is_available():
        """ Return True if the native module is present, False otherwise.
        """
        return waf is not None


class WAFCB(WAFCBMixin, RuleCallback):
    """ WAF Callback
    """

    def __init__(self, *args, **kwargs):
        super(WAFCB, self).__init__(*args, **kwargs)
        bas = {}
        values = self.data.get("values", {})
        for item in values.get("binding_accessors", []):
            if isinstance(item, Mapping):
                bas[item["ba"]] = (BindingAccessor(item["ba"]), item.get("default", None))
            else:
                bas[item] = (BindingAccessor(item), None)
        self.binding_accessors = bas

    def pre(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        if request is None:
            return

        budget = self.get_remaining_budget(options)
        if budget is None:
            budget = self.max_budget_ms

        binding_eval_args = {
            "request": request,
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
        }

        params = {}
        for expr, (ba, default) in self.binding_accessors.items():
            with self.storage.trace() as trace:
                try:
                    res = ba.resolve(**binding_eval_args)
                    params[expr] = default if res is None else res
                except (ValueError, KeyError, AttributeError):
                    params[expr] = default
            budget -= trace.duration_ms
            if budget <= 0:
                LOGGER.debug("skipping WAF because %r evaluation is overtime", expr)
                return

        return self.execute(self._inst, params, budget)

    def record_waf_attack(self, waf_data, **kwargs):
        """ Enrich the attack info with the current agent type."""
        self.record_attack(
            infos={"waf_data": waf_data, "ba_type": get_agent_type()},
            **kwargs
        )
