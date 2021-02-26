# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import logging
from collections import defaultdict, deque
from datetime import timedelta
from itertools import groupby
from operator import itemgetter

from .config import CONFIG
from .events import RequestRecord
from .performance_metrics import RequestTrace, Trace
from .runner import MetricsEvent
from .utils import now

LOGGER = logging.getLogger(__name__)


class RequestRecorder:
    """Store observations related to a request."""

    def __init__(self):
        # Traces can be recorded out of a request, we keep the traces
        # in the request recorder while waiting for the flush call. If there
        # is no request for a while, the traces could pile up, so we limit their
        # number and keep only the latest.
        self.traces = deque(maxlen=CONFIG["MAX_OBS_QUEUE_LENGTH"])
        self.clear()

    def clear(self):
        """Clear all observations."""
        self.report = False
        self.payload_sections = set()
        self.observations = defaultdict(list)
        self.traces.clear()
        self.request_trace = None
        self.request_overtime = False

    def trace(self, name=None):
        """Start a new trace from a request trace."""
        if self.request_trace is None:
            # There is not request at the moment, use a independant trace.
            return Trace(name, recorder=self)
        return self.request_trace.trace(name)

    def start_request(self, request, trace_request=False):
        """Start a request."""
        if trace_request:
            self.request_trace = RequestTrace(recorder=self)

    def end_request(self):
        """End the current request."""
        if self.request_trace is not None:
            self.request_trace.end()

    def record_trace(self, name, start_time, value, at):
        """Record a performance metric."""
        if name is not None:
            self.traces.append((name, at, None, value))

    @property
    def request_sq_time(self):
        """Total time spent in callbacks during a request."""
        if self.request_trace is not None:
            return self.request_trace.aggregated_duration_ms

    def record_overtime(self, name, at):
        """Record which callback triggered the overtime."""
        if not self.request_overtime and self.request_trace is not None:
            at = now() if at is None else at
            self.observe(
                "observations",
                ("request_overbudget_cb", at, name, 1),
                report=False
            )
            self.request_overtime = True

    def observe(self, what, observation, payload_sections=None, report=True):
        """Record an observation."""
        self.observations[what].append(observation)
        if payload_sections:
            self.payload_sections.update(payload_sections)
        if report:
            self.report = True

    def flush(self, request, response, payload_creator, queue, observation_queue):
        """Flush all observations."""
        self._put_metrics(queue, observation_queue)
        if self.report:
            payload = payload_creator.get_payload(
                request, response, self.payload_sections
            )
            # If request recorder must report the request, send also the
            # detailed observations.
            payload["observed"] = self.observations
            queue.put(RequestRecord(payload))
        self.clear()

    def _put_metrics(self, queue, observation_queue):
        if LOGGER.isEnabledFor(logging.DEBUG):
            it = sorted([(t[0], (t[1] - timedelta(seconds=t[3] / 1000.0))
                          if t[0].startswith("sq.") else t[1], t[2], t[3])
                         for t in self.traces], key=itemgetter(1))
            metrics = []
            for key, group in groupby(it, key=itemgetter(0)):
                group = list(group)
                line = ""
                if key.startswith("sq."):
                    line += str(group[0][1])
                line += "\t{0}: ".format(key)
                line += " ".join("{0:.02f}".format(i[3]) for i in group)
                if len(group) > 1:
                    line += " ({:.02f} total)".format(sum(i[3] for i in group))
                metrics.append(line)
            if self.request_overtime:
                metrics.append("\trequest was overbudget")
            if metrics:
                LOGGER.debug("Performance metrics:\n%s", "\n".join(metrics))

        # Send the performance metrics to observation queue for aggregation
        while self.traces:
            observation_queue.put(self.traces.popleft())

        # Aggregate metric observations
        for observation in self.observations.pop("observations", []):
            observation_queue.put(observation)
        if observation_queue.half_full():
            queue.put(MetricsEvent)
