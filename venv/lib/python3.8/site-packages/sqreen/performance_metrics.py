# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import time
from datetime import datetime
from logging import getLogger

from .utils import UTC, naive_dt_to_utc, now

DEFAULT_PERF_LEVEL = 0  # 0: disabled; 1: enabled
DEFAULT_PERF_PERIOD = 60
DEFAULT_PERF_BASE = 2.0
DEFAULT_PERF_UNIT = 0.1  # ms
DEFAULT_PERF_PCT_BASE = 1.3
DEFAULT_PERF_PCT_UNIT = 1.0  # %
DEFAULT_OVERTIME_PERIOD = 60

LOGGER = getLogger(__name__)


class PerformanceMetricsSettings:
    """ Performance metrics settings.
    """

    SETTINGS_FIELD_MAP = {
        'perf_level': 'level',
        'performance_metrics_period': 'period',
        'perf_base': 'base',
        'perf_unit': 'unit',
        'perf_pct_base': 'pct_base',
        'perf_pct_unit': 'pct_unit',
        'request_overtime_metric_period': 'overtime_period',
    }

    def __init__(self, level=DEFAULT_PERF_LEVEL,
                 period=DEFAULT_PERF_PERIOD,
                 base=DEFAULT_PERF_BASE,
                 unit=DEFAULT_PERF_UNIT,
                 pct_base=DEFAULT_PERF_PCT_BASE,
                 pct_unit=DEFAULT_PERF_PCT_UNIT,
                 overtime_period=DEFAULT_OVERTIME_PERIOD):
        self.level = level
        self.period = period
        self.base = base
        self.unit = unit
        self.pct_base = pct_base
        self.pct_unit = pct_unit
        self.overtime_period = overtime_period
        if self.enabled() and self.period == 0:
            LOGGER.warning("Setting performance period to default %d",
                           DEFAULT_PERF_PERIOD)
            self.period = DEFAULT_PERF_PERIOD

    @staticmethod
    def from_features(features):
        level = features.get('perf_level', DEFAULT_PERF_LEVEL)
        # old name, in Ruby not used for binned metrics:
        period = features.get('performance_metrics_period', DEFAULT_PERF_PERIOD)
        base = features.get('perf_base', DEFAULT_PERF_BASE)
        unit = features.get('perf_unit', DEFAULT_PERF_UNIT)
        pct_base = features.get('perf_pct_base', DEFAULT_PERF_PCT_BASE)
        pct_unit = features.get('perf_pct_unit', DEFAULT_PERF_PCT_UNIT)
        overtime_period = features.get('request_overtime_metric_period', DEFAULT_OVERTIME_PERIOD)

        return PerformanceMetricsSettings(level=level, period=period,
                                          base=base, unit=unit,
                                          pct_base=pct_base, pct_unit=pct_unit,
                                          overtime_period=overtime_period)

    def as_features(self):
        return {k: getattr(self, v) for k, v in self.SETTINGS_FIELD_MAP.items()}

    def enabled(self):
        return self.level > 0


class Trace(object):
    """Trace execution time."""

    def __init__(self, name=None, recorder=None, at=None):
        self.name = name
        self.recorder = recorder
        # TODO use a monotonic clock but there is none on Python < 3.3.
        # Maybe work around this with a native extension.
        if at is None:
            self.start_time = time.time()
        else:
            at = naive_dt_to_utc(at)
            self.start_time = (at - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds()
        self.duration = None

    @property
    def start_at(self):
        """Get the datetime associated with the start time."""
        return datetime.fromtimestamp(self.start_time, tz=UTC)

    @property
    def duration_ms(self):
        """Convert the duration from seconds to milliseconds."""
        if self.duration is not None:
            return self.duration * 1000

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.end()
        except Exception:
            LOGGER.error("exception while ending a performance trace", exc_info=1)

    def end(self, at=None):
        """End a performance trace."""
        if self.duration is not None:
            return
        if at is None:
            end_time = time.time()
        else:
            at = naive_dt_to_utc(at)
            end_time = (at - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds()
        self.duration = end_time - self.start_time
        if self.duration < 0:
            self.duration = 0
        if self.recorder is not None:
            if at is None:
                at = datetime.fromtimestamp(end_time, tz=UTC)
            self.recorder.record_trace(self.name, self.start_time, self.duration_ms, at)

    def __repr__(self):
        return "<{} name={!r} duration_ms={:.4f}>".format(
            self.__class__.__name__,
            self.name,
            self.duration_ms
        )


class AggregatedDuration:
    """Compute total duration of potentially overlapping traces.
    """

    def __init__(self):
        self._start_time = 0
        self._counter = 0
        self._duration = 0

    def push_start(self, current_time):  # type: (float) -> None
        if self._counter == 0:
            self._start_time = current_time
            self._counter = 1
        else:
            self._counter += 1

    def push_stop(self, current_time):  # type: (float) -> None
        if self._counter == 1:
            self._duration += current_time - self._start_time
            self._counter = 0
        elif self._counter > 0:
            self._counter -= 1

    def get_duration(self, current_time):  # type: (float) -> float
        if self._counter > 0:
            # Still active spans, compute duration with current time
            return self._duration + (current_time - self._start_time)
        return self._duration


class RequestTrace(Trace):
    """Trace request execution time for performance monitoring.

    Sub traces can be created for monitoring rule execution
    time. When the request is terminated, the total rule execution
    time is computed. Beware, a sub trace cannot survive this trace,
    meaning when the end method is called, all sub-traces are ended too.
    """

    def __init__(self, recorder=None, at=None):
        self._traces = []
        self._aggregated_duration = AggregatedDuration()
        super(RequestTrace, self).__init__("req", recorder, at=at)

    def trace(self, name=None, at=None):
        """Start a sub-trace."""
        trace = Trace(name, at=at, recorder=self)
        self._aggregated_duration.push_start((trace.start_time - self.start_time) * 1000.0)
        self._traces.append(trace)
        return trace

    @property
    def aggregated_duration_ms(self):
        """Return total time spent in sub-traces."""
        duration = self._aggregated_duration.get_duration((time.time() - self.start_time) * 1000.0)
        return duration if duration > 0 else 0

    def record_trace(self, name, start_time, duration, at):
        """Aggregate values from sub-traces."""
        self._aggregated_duration.push_stop((start_time - self.start_time) * 1000.0 + duration)
        if self.recorder is not None:
            self.recorder.record_trace(name, start_time, duration, at)

    def end(self, at=None):
        """End the trace and all sub traces."""
        # Automatically terminate sub traces to assure consistency
        if at is None:
            at = now()
        for trace in self._traces:
            if trace.duration is None:
                trace.end(at=at)
        super(RequestTrace, self).end(at=at)
        if self.recorder is not None:
            duration_ms = self.duration_ms
            aggregated_duration_ms = self._aggregated_duration.get_duration(duration_ms)
            self.recorder.record_trace("sq", None, aggregated_duration_ms, at)
            no_sq = duration_ms - aggregated_duration_ms
            if no_sq > 0:
                fraction = self.aggregated_duration_ms / no_sq
                self.recorder.record_trace("pct", None, 100.0 * fraction, at)
