# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Callbacks rules classes and helpers
"""
import logging
from functools import wraps

from .condition_evaluator import ConditionEvaluator, is_condition_empty
from .remote_exception import raw_traceback_formatter, traceback_formatter
from .runtime_storage import runtime
from .samplers import ScopedTracingSampler
from .utils import now

LOGGER = logging.getLogger(__name__)


class BaseCallback(object):
    """ Base class for callbacks.
    """

    DEFAULT_EXCEPTION_SECTIONS = ("request", "response", "params", "headers", "context")

    SUPPORTS_BUDGET = False  # override constants in subclasses supporting it
    INTERRUPTIBLE = True

    def __init__(
        self,
        rule_name,
        rulespack_id,
        runner,
        beta=None,
        block=None,
        test=None,
        data=None,
        metrics=None,
        payload_sections=None,
        priority=None,
        attack_type=None,
        sampling=None,
        storage=None,
    ):
        self.rule_name = rule_name
        self.rulespack_id = rulespack_id
        self.runner = runner

        self.data = data or {}
        self.beta = beta or False
        self.block = block or False
        self.test = test or False
        self.metrics = metrics or []
        self.sampling = sampling
        self.storage = storage or runtime

        self.attack_type = attack_type

        self.payload_sections = payload_sections

        # Priority (lower number means higher priority)
        self.priority = priority if priority is not None else 100

    @property
    def collaborative(self):
        """Is the callback collaborative and support running with a budget."""
        return self.SUPPORTS_BUDGET

    @property
    def skippable(self):
        """Allow the callback to be skipped if request is overtime."""
        return self.INTERRUPTIBLE

    @property
    def whitelisted(self):
        """ Return True if the callback should be skipped (whitelisted
        request), False otherwise
        """
        return self.storage.get_whitelist_match() or False

    @property
    def performance_monitoring_enabled(self):
        """ Return True if the performance monitoring is enabled for this rule.
        """
        if self.runner is not None:
            return self.runner.performance_metrics and self.runner.performance_metrics_settings.enabled()
        return False

    def action_processor(self, result_action, options):
        """ Return the callback method results.
        """
        return result_action

    def _apply_action_processor(self, methods):
        for lifecycle in methods:
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None:
                wrapped = action_processor_wrapper(lifecycle_method, self)
                setattr(self, lifecycle, wrapped)

    def _apply_debug_log(self, methods):
        if not LOGGER.isEnabledFor(logging.DEBUG):
            return

        for lifecycle in methods:
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None:
                wrapped = debug_log_wrapper(lifecycle_method, lifecycle, self)
                setattr(self, lifecycle, wrapped)

    def _apply_perf_monitoring(self, methods):
        # Only enable the performance monitoring if the feature flag is
        if not self.performance_monitoring_enabled:
            return

        for lifecycle in methods:
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None:
                metric_name = "sq.{}.{}".format(self.rule_name, lifecycle)
                wrapped = perf_monitoring_wrapper(
                    lifecycle_method, self.storage, metric_name)
                setattr(self, lifecycle, wrapped)

    def _apply_sampling(self, methods):
        """ Wrap each lifecycle methods if the Rule define them and if we have
        sampling on the rule.
        """
        sampling = self.sampling
        if sampling is None:
            return

        # XXX this is to circumvent a problem with rules defaulting to an empty sampling list
        # instead of using null.
        if not sampling:
            return

        sampler = ScopedTracingSampler({"enabled": True, "sampling": sampling})
        for lifecycle in methods:
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None:
                wrapped = sampling_wrapper(
                    lifecycle_method, self, sampler, lifecycle)
                setattr(self, lifecycle, wrapped)

    def get_remaining_budget(self, callback_options=None):
        """ Get the remaining time we have for running this callback according
        to the request budget if there is one. The budget can be overriden
        with a special option in options. Return None otherwise.
        """
        if callback_options is not None:
            override_budget = callback_options.pop("__sqreen_override_budget", None)
            if override_budget is not None:
                return override_budget
        if self.runner is not None and self.performance_monitoring_enabled:
            budget = self.runner.budget
            if budget is not None:
                return budget - (self.storage.request_sq_time or 0)

    def exception_infos(self, infos={}):
        """ Returns additional infos in case of exception
        """
        return {"rule_name": self.rule_name, "rulespack_id": self.rulespack_id}

    def record_exception(self, exc, exc_info, stack=None, infos=None, at=None):
        """Record an exception."""
        if infos is None:
            infos = {}
        if at is None:
            at = now()
        # Try to recover some infos from the exception if it's a
        # SqreenException.
        try:
            infos.update(exc.exception_infos())
        except Exception:
            pass
        bt = raw_traceback_formatter(exc_info[2])
        if stack is not None:
            bt = traceback_formatter(stack) + bt
        payload = {
            "message": str(exc_info[1]),
            "klass": exc_info[0].__name__,
            "infos": infos,
            "rule_name": self.rule_name,
            "rulespack_id": self.rulespack_id,
            "test": self.test,
            "time": at,
            "backtrace": bt,
        }
        LOGGER.debug("Observed exception %r", payload)
        payload_sections = self.payload_sections
        if payload_sections is None:
            payload_sections = self.DEFAULT_EXCEPTION_SECTIONS
        self.storage.observe("sqreen_exceptions", payload,
                             payload_sections=payload_sections, report=True)

    def record_overtime(self, lifecycle, at=None):
        """Record an overtime execution."""
        self.storage.record_overtime(
            "{}.{}".format(self.rule_name, lifecycle), at=at)

    def __repr__(self):
        return "%s(rule_name=%r)" % (
            self.__class__.__name__, self.rule_name)


def sampling_wrapper(wrapped, callback, sampler, lifecycle):
    """ Wrapper that will execute the sampler to know if
    the callback must be executed, otherwise return None.
    """

    @wraps(wrapped)
    def wrapper(inst, args, kwargs, options):
        decisions = options.get("sampling_decisions")
        if decisions is None:
            decisions = options["sampling_decisions"] = {}
        # Has the sampler already been evaluated for this callback?
        decision = decisions.get(callback.rule_name)
        if decision is None:
            # else shall we execute the callback?
            decision = decisions[callback.rule_name] = sampler.should_sample(**options)
        if decision:
            # proceed with callback execution
            return wrapped(inst, args, kwargs, options)

    wrapper.__wrapped__ = wrapped
    return wrapper


def check_condition_wrapper(wrapped, callback, condition, lifecycle):
    """ Wrapper that will check lifecycle method pre-condition before
    calling it.
    If pre-conditions are true, call the lifecycle method, otherwise
    return None.
    """

    @wraps(wrapped)
    def wrapper(inst, args, kwargs, options):
        """ Wrapper around lifecycle method
        """
        storage = callback.storage

        # Compute return value depending on the lifecycle method we wrap
        rv = options.get("result" if lifecycle == "post" else "exc_info")

        binding_eval_args = {
            "request": storage.get_current_request(),
            "response": storage.get_current_response(),
            "inst": inst,
            "args": storage.get_current_args(args),
            "kwargs": kwargs,
            "data": callback.data,
            "rv": rv,
            "request_store": storage.get_request_store(),
            "options": options,
        }

        # Check the pre condition
        condition_result = condition.evaluate(**binding_eval_args)

        if condition_result in (False, None):
            LOGGER.debug(
                "Not running %r on %r: %r is %s",
                lifecycle,
                callback,
                condition,
                condition_result,
            )
            return None

        # Execute the hook otherwise with the original args
        return wrapped(inst, args, kwargs, options)

    wrapper.__wrapped__ = wrapped
    return wrapper


def call_count_wrapper(wrapped, callback, lifecycle, observation_key):
    """ Wrapper around lifecycle methods that record number of calls
    """

    @wraps(wrapped)
    def wrapper(inst, args, kwargs, options):
        """ Record the number of calls for this callback lifecycle method.
        Buffer the number in the callback itself (self.call_counts) and record
        an observation every X times, X being the field call_count_interval of
        the rule.
        """
        current_count = callback.call_counts[lifecycle]

        if current_count + 1 == callback.call_count_interval:
            # We do not need to pass by the request recorder here.
            callback.runner.observation_queue.put(
                ["sqreen_call_counts", options.get("at") or now(), observation_key, callback.call_count_interval]
            )
            callback.call_counts[lifecycle] = 0
        else:
            callback.call_counts[lifecycle] += 1

        return wrapped(inst, args, kwargs, options)

    wrapper.__wrapped__ = wrapped
    return wrapper


def perf_monitoring_wrapper(wrapped, storage, name):
    """ Wrapper that will monitor the performance of the rule callback.
    It will time the execution of the callback and send it as an
    observation metric.

    The wrapper should be called first before every others.
    """

    @wraps(wrapped)
    def wrapper(inst, args, kwargs, options):
        """ Time the callback execution and update the at option entry.
        """
        with storage.trace(name) as t:
            options["at"] = t.start_at
            return wrapped(inst, args, kwargs, options)

    wrapper.__wrapped__ = wrapped
    return wrapper


def debug_log_wrapper(wrapped, lifecycle, callback):

    @wraps(wrapped)
    def wrapper(*args, **kwargs):
        LOGGER.debug("Running %r on callback %r", lifecycle, callback)
        return wrapped(*args, **kwargs)

    wrapper.__wrapped__ = wrapped
    return wrapper


def action_processor_wrapper(wrapped, callback):

    @wraps(wrapped)
    def wrapper(inst, args, kwargs, options):
        return callback.action_processor(wrapped(inst, args, kwargs, options), options)

    wrapper.__wrapped__ = wrapped
    return wrapper


class RuleCallback(BaseCallback):
    """Rule callback attached to a hookpoint.

    The hook_name is the path to the hook, it could be either a module, like
    "package.module", or a specific class "package.module::Class".
    The hook_name is the name of the function to hook_on, it's relative to
    the hook_module, for example with a hook_module equal to
    "package.module::Class" and a hook_path equal to "method", we will
    hook on the method named "method" of a class named "Class" in the module
    named "package.module"
    """

    def __init__(
        self,
        hook_module,
        hook_name,
        rule_name,
        rulespack_id,
        runner,
        beta=False,
        block=False,
        test=False,
        strategy=None,
        data=None,
        conditions=None,
        callbacks=None,
        call_count_interval=None,
        metrics=None,
        payload_sections=None,
        priority=None,
        attack_render_info=None,
        attack_type=None,
        sampling=None,
        storage=runtime,
    ):
        self.hook_module = hook_module
        self.hook_name = hook_name
        self.strategy = strategy

        super(RuleCallback, self).__init__(
            rule_name=rule_name,
            rulespack_id=rulespack_id,
            runner=runner,
            beta=beta,
            block=block,
            test=test,
            data=data,
            metrics=metrics,
            payload_sections=payload_sections,
            priority=priority,
            attack_type=attack_type,
            sampling=sampling,
            storage=storage,
        )
        self.attack_render_info = attack_render_info

        if conditions is None:
            conditions = {}
        self.conditions = conditions

        if callbacks is None:
            callbacks = {}
        self.callbacks = callbacks

        # Callbacks
        self.call_count_interval = call_count_interval or 0
        self.call_counts = {"pre": 0, "post": 0, "failing": 0}

        methods = self.lifecycle_methods
        self._apply_action_processor(methods)
        self._apply_debug_log(methods)
        self._apply_conditions(methods)
        self._apply_sampling(methods)
        self._apply_call_count(methods)
        self._apply_perf_monitoring(methods)

    @classmethod
    def from_rule_dict(cls, rule_dict, runner, storage=None):
        """ Return a RuleCallback based on a rule dict
        """
        return cls(
            hook_module=rule_dict["hookpoint"]["klass"],
            hook_name=rule_dict["hookpoint"]["method"],
            rule_name=rule_dict["name"],
            rulespack_id=rule_dict["rulespack_id"],
            strategy=rule_dict["hookpoint"].get("strategy", "import_hook"),
            attack_render_info=rule_dict["hookpoint"].get("attack_render_info", {}),
            beta=rule_dict.get("beta"),
            block=rule_dict.get("block"),
            test=rule_dict.get("test"),
            data=rule_dict.get("data"),
            conditions=rule_dict.get("conditions"),
            callbacks=rule_dict.get("callbacks"),
            call_count_interval=rule_dict.get("call_count_interval"),
            runner=runner,
            metrics=rule_dict.get("metrics"),
            payload_sections=rule_dict.get("payload"),
            priority=rule_dict.get("priority"),
            attack_type=rule_dict.get("attack_type"),
            sampling=rule_dict.get("sampling"),
            storage=storage,
        )

    def _apply_conditions(self, methods):
        """ Wrap each lifecycle methods if the Rule define them and if we have
        conditions for them.
        """
        for lifecycle in methods:
            conditions = self.conditions.get(lifecycle)
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None and \
                    not is_condition_empty(conditions):
                conditions = ConditionEvaluator(conditions)
                # Wrap the lifecycle method
                wrapped = check_condition_wrapper(
                    lifecycle_method, self, conditions, lifecycle)
                setattr(self, lifecycle, wrapped)

    def _apply_call_count(self, methods):
        # Only count calls if call_count_interval is > 0
        if self.call_count_interval == 0:
            return

        for lifecycle in methods:
            lifecycle_method = getattr(self, lifecycle, None)
            if lifecycle_method is not None:

                observation_key = "%s/%s/%s" % (
                    self.rulespack_id,
                    self.rule_name,
                    lifecycle,
                )

                wrapped = call_count_wrapper(
                    lifecycle_method, self, lifecycle, observation_key)
                setattr(self, lifecycle, wrapped)

    @property
    def lifecycle_methods(self):
        return [lifecycle for lifecycle in ("pre", "post", "failing",)
                if hasattr(self, lifecycle)]

    def __repr__(self):
        return "%s(rule_name=%r, hook_module=%r, hook_name=%r, strategy=%r)" % (
            self.__class__.__name__, self.rule_name, self.hook_module,
            self.hook_name, self.strategy)


class ReactiveRuleCallback(BaseCallback):
    """ Rule callbacks attached to data subscribed on the reactive engine.
    """

    def __init__(
        self,
        rule_name,
        rulespack_id,
        runner,
        beta=False,
        block=False,
        test=False,
        data=None,
        authorized_addresses=None,
        metrics=None,
        payload_sections=None,
        priority=None,
        attack_type=None,
        sampling=None,
        storage=runtime,
    ):
        super(ReactiveRuleCallback, self).__init__(
            rule_name=rule_name,
            rulespack_id=rulespack_id,
            runner=runner,
            beta=beta,
            block=block,
            test=test,
            data=data,
            metrics=metrics,
            payload_sections=payload_sections,
            priority=priority,
            attack_type=attack_type,
            sampling=sampling,
            storage=storage,
        )
        self.authorized_addresses = frozenset(authorized_addresses or [])
        self.batch_addresses = self.authorized_addresses
        self.group_addresses = frozenset()

        self._apply_action_processor(["handler"])
        self._apply_debug_log(["handler"])
        self._apply_sampling(["handler"])
        self._apply_perf_monitoring(["handler"])

    def handler(self, instance, args, kwargs, options):
        """ Handler called when addresses are available.
        """
        raise NotImplementedError

    @classmethod
    def from_rule_dict(cls, rule_dict, runner, storage=None):
        """ Return a ReactiveRuleCallback based on a rule dict
        """
        return cls(
            rule_name=rule_dict["name"],
            rulespack_id=rule_dict["rulespack_id"],
            beta=rule_dict.get("beta"),
            block=rule_dict.get("block"),
            test=rule_dict.get("test"),
            data=rule_dict.get("data"),
            authorized_addresses=rule_dict.get("reactive", {}).get("authorized_addresses"),
            runner=runner,
            metrics=rule_dict.get("metrics"),
            payload_sections=rule_dict.get("payload"),
            priority=rule_dict.get("priority"),
            attack_type=rule_dict.get("attack_type"),
            sampling=rule_dict.get("sampling"),
            storage=storage,
        )
