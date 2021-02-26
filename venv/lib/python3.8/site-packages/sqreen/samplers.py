# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Thread-safe samplers
"""

import itertools
import random
import threading
from collections import namedtuple
from datetime import timedelta

from .utils import HAS_TYPING, now

if HAS_TYPING:
    from datetime import datetime
    from typing import Any, Dict, Optional, Sequence


class Decision(namedtuple("Decision", ["sampled", "attrs"])):

    __slots__ = ()

    def __new__(cls, sampled, attrs=None):  # type: (bool, Optional[Dict]) -> "Decision"
        if attrs is None:
            attrs = {}
        return super(Decision, cls).__new__(cls, sampled, attrs)

    def __nonzero__(self):
        return self.sampled

    def __bool__(self):
        return self.sampled


class BaseSampler(object):

    def should_sample(self, **kwargs):  # type (**Any) -> Decision
        raise NotImplementedError


class CallSampler(BaseSampler):

    def __init__(self, n_calls):  # type (int) -> None
        self.n_calls = n_calls
        self._state = itertools.count()

    def should_sample(self, **kwargs):  # type (**Any) -> Decision
        state = next(self._state)
        return Decision(state % self.n_calls == 0, dict(counter=state))


class MaxCallSampler(BaseSampler):

    def __init__(self, max_calls):  # type (int) -> None
        self.max_calls = max_calls
        self._state = itertools.count()

    def should_sample(self, **kwargs):  # type (**Any) -> Decision
        state = next(self._state)
        return Decision(state < self.max_calls, dict(counter=state))


class ProbabilitySampler(BaseSampler):

    def __init__(self, rate):  # type: (float) -> None
        if rate < 0:
            raise ValueError("rate cannot be negative")
        if rate > 1:
            rate = 1.0
        self.rate = rate

    def should_sample(self, random_value=None, **kwargs):  # type (Optional[float], **Any) -> Decision
        if random_value is None:
            random_value = random.random()
        return Decision(random_value < self.rate, dict(random_value=random_value))


class MaxCallWindowSampler(MaxCallSampler):

    def __init__(self, max_calls, window_duration_s):  # type: (int, float) -> None
        super(MaxCallWindowSampler, self).__init__(max_calls)
        self.window_duration_s = timedelta(seconds=window_duration_s)
        self._window_started_at = None
        self._lock = threading.Lock()

    def should_sample(self, at=None, **kwargs):  # type (Optional[datetime], **Any) -> Decision
        with self._lock:
            if at is None:
                at = now()
            if self._window_started_at is None or at - self._window_started_at >= self.window_duration_s:
                self._window_started_at = at
                self._state = itertools.count()
            attrs = dict(window_started_at=self._window_started_at, at=at)
        decision = super(MaxCallWindowSampler, self).should_sample(**kwargs)
        decision.attrs.update(attrs)
        return decision


class MaxDurationSampler(BaseSampler):

    def __init__(self, max_duration_s, at=None):  # type: (float, Optional[datetime]) -> None
        if at is None:
            at = now()
        self._max_duration_at = at + timedelta(seconds=max_duration_s)

    def should_sample(self, at=None, **kwargs):  # type: (Optional[datetime], **Any) -> Decision
        if at is None:
            at = now()
        return Decision(at < self._max_duration_at, dict(at=at))


class AnySampler(BaseSampler):

    def __init__(self, samplers):  # type: (Sequence[BaseSampler]) -> None
        self.samplers = samplers

    def should_sample(self, **kwargs):  # type: (**Any) -> Decision
        try:
            idx, decision = next(
                (idx, decision) for idx, decision in
                enumerate(sampler.should_sample(**kwargs) for sampler in self.samplers)
                if decision
            )
            return Decision(True, dict(idx=idx, child=decision))
        except StopIteration:
            return Decision(False)


class AllSampler(BaseSampler):

    def __init__(self, samplers):  # type: (Sequence[BaseSampler]) -> None
        self.samplers = samplers

    def should_sample(self, **kwargs):  # type: (**Any) -> Decision
        children = list([sampler.should_sample(**kwargs) for sampler in self.samplers])
        return Decision(all(children), dict(children=children))


class LineTracingSampler(AllSampler):

    def __init__(self, line):
        samplers = []
        line = dict(line)
        n_calls = line.pop("calls", None)
        if n_calls is not None:
            samplers.append(CallSampler(n_calls))
        rate = line.pop("random", None)
        if rate is not None:
            samplers.append(ProbabilitySampler(rate))
        max_duration_m = line.pop("max_duration_minutes", None)
        if max_duration_m is not None:
            samplers.append(MaxDurationSampler(max_duration_m * 60))
        target_per_m = line.pop("target_per_minute", None)
        if target_per_m is not None:
            samplers.append(MaxCallWindowSampler(target_per_m, 60))
        max_calls = line.pop("max_calls", None)
        if max_calls is not None:
            samplers.append(MaxCallSampler(max_calls))
        if line:
            # Unknown primitives remaining, always False
            samplers.insert(0, AnySampler({}))
        super(LineTracingSampler, self).__init__(samplers)


class ScopedTracingSampler(AnySampler):

    def __init__(self, definition):
        enabled = definition.get("enabled")
        if enabled:
            self.instruction = definition.get("sampling", [{}])
            samplers = [LineTracingSampler(line) for line in self.instruction]
        else:
            self.instruction = []
            samplers = []
        super(ScopedTracingSampler, self).__init__(samplers)

    def should_sample(self, **kwargs):
        decision = super(ScopedTracingSampler, self).should_sample(**kwargs)
        if decision:
            decision.attrs["trigger"] = self.instruction[decision.attrs["idx"]]
        return decision


class TracingSampler(BaseSampler):

    def __init__(self, scope_definition={}):
        scope_definition = dict(scope_definition)
        default_definition = scope_definition.pop("*", {})
        self.default_sampler = ScopedTracingSampler(default_definition)
        self.samplers = {scope: ScopedTracingSampler(definition)
                         for scope, definition in scope_definition.items()}

    def should_sample(self, scope=None, **kwargs):  # type: (Optional[str], **Any) -> Decision
        sampler = self.samplers.get(scope)
        if sampler is not None:
            return sampler.should_sample(**kwargs)
        return self.default_sampler.should_sample(**kwargs)

    def update_scope_definition(self, scope_definition):
        """ Update the current scope definition with a new scope definition.
        """
        obj = self.__class__(scope_definition)
        new_samplers = dict(self.samplers)
        new_samplers.update(obj.samplers)
        if "*" in scope_definition:
            self.default_sampler = obj.default_sampler
        self.samplers = new_samplers
