# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Main runner module
"""

import itertools
import logging
import sys
from time import time

from .config import CONFIG
from .deliverer import get_deliverer
from .ip_radix import Radix
from .list_filters import RequestPrefixListFilter
from .metrics import UnregisteredMetric
from .performance_metrics import PerformanceMetricsSettings
from .samplers import TracingSampler
from .utils import now

if sys.version_info[0] < 3:
    from Queue import Empty, Full, Queue
else:
    from queue import Empty, Full, Queue

LOGGER = logging.getLogger(__name__)


class RunnerStop(object):
    """ Placeholder event for asking the runner to stop
    """


class MetricsEvent(object):
    """ Placeholder for asking observations aggregation to run
    """


class CappedQueue(object):
    """ Capped queue with opiniatied methods
    """

    def __init__(self, maxsize=None, name=None):
        if maxsize is None:
            maxsize = CONFIG["MAX_QUEUE_LENGTH"]

        self.maxsize = maxsize
        self.queue = Queue(self.maxsize)
        self.name = name or "queue"
        self._count_ingress = itertools.count()
        self._count_dropped = itertools.count()
        self._count_egress = itertools.count()
        self._last_count_ingress = 0
        self._last_count_dropped = 0
        self._last_count_egress = 0

    def get(self, timeout, block=True):
        """ Wait for up to timeout for an item to return and block while
        waiting
        """
        ret = self.queue.get(timeout=timeout, block=block)
        next(self._count_egress)
        return ret

    def get_nowait(self):
        """ Get without waiting, raise queue.Empty if nothing is present
        """
        ret = self.queue.get_nowait()
        next(self._count_egress)
        return ret

    def put(self, item):
        """ Tries to put an item to the queue, if the queue is full, pop an
        item and try again
        """
        while True:
            try:
                ret = self.queue.put_nowait(item)
                next(self._count_ingress)
                return ret
            except Full:
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                    next(self._count_dropped)
                except Empty:
                    pass

    def half_full(self):
        """ Return True if the current queue size if at least half the maxsize
        """
        return self.queue.qsize() > (self.maxsize / 2.)

    def get_metrics(self, at=None):
        """ Return the queue metrics, this method is *NOT* thread-safe.
        """
        ingress_delta = next(self._count_ingress) - self._last_count_ingress
        dropped_delta = next(self._count_dropped) - self._last_count_dropped
        egress_delta = next(self._count_egress) - self._last_count_egress
        self._last_count_ingress += ingress_delta + 1
        self._last_count_dropped += dropped_delta + 1
        self._last_count_egress += egress_delta + 1
        at = at or now()
        return [
            ("event_manager", at, "{}_ingress".format(self.name), ingress_delta),
            ("event_manager", at, "{}_dropped".format(self.name), dropped_delta),
            ("event_manager", at, "{}_egress".format(self.name), egress_delta),
        ]

    def task_done(self):
        """ Inform the queue that an event was processed.
        """
        self.queue.task_done()

    def join(self):
        """ Block until all events are consumed
        """
        self.queue.join()


class RunnerSettings(object):
    """ Various values that need to be shared across threads
    """

    def __init__(self):
        self.ips_whitelist = Radix(None)
        self.paths_whitelist = RequestPrefixListFilter()
        self.debug_flag = None
        self.tracing_identifier_prefix = None

    def set_ips_whitelist(self, addresses):
        """ Replace the current list of whitelisted IP networks
        """
        new_ips_whitelist = Radix(None)
        for address in addresses:
            new_ips_whitelist.insert(address, '/' in address)
        self.ips_whitelist = new_ips_whitelist

    def ips_whitelist_match(self, address):
        """ Return the first matching IP network, or None if no match could be
        found.
        """
        if address:
            return self.ips_whitelist.match(address)

    def set_paths_whitelist(self, paths):
        """ Replace the current list of whitelisted request path prefixes
        """
        self.paths_whitelist.reset(paths)

    def paths_whitelist_match(self, path):
        """ Return the first matching request path prefix, or None if no match
        could be found.
        """
        if path is not None:
            return self.paths_whitelist.match(path)

    def whitelist_match(self, request):
        """ Return the first matching IP network or request path prefix, or
        None if no match could be found.
        """
        ip = self.ips_whitelist_match(request.raw_client_ip)
        if ip is not None:
            return ip
        prefix = self.paths_whitelist_match(request.path)
        if prefix is not None:
            return prefix

    def set_debug_flag(self, flag):
        """ Set to True if the framework is in debug mode.
        """
        self.debug_flag = flag

    def get_debug_flag(self):
        """ Get the current debug flag.
        """
        return self.debug_flag

    def set_tracing_identifier_prefix(self, tracing_identifier_prefix):
        """ Set the current tracing idenftifier prefix.
        """
        self.tracing_identifier_prefix = tracing_identifier_prefix


def process_initial_commands(initial_payload, runner):
    """ Process the initial non-standard login payload
    """
    commands = initial_payload.get("commands", [])
    rulespack_id = initial_payload.get("pack_id", None)
    rules = initial_payload.get("rules", [])

    # Preprocess commands first
    for command in commands:
        if command["name"] == "instrumentation_enable":
            params = command.get("params")
            if not params:
                command["params"] = (rulespack_id, rules)
            break
    else:
        # Always instrument even without a rulespack
        # in fact, some frameworks require a very early
        # instrumentation and cannot wait the next heartbeat.
        commands.append({
            "uuid": "static-instrumentation-enable",
            "name": "instrumentation_enable",
            "params": (rulespack_id, rules),
        })

    # Process commands normally
    runner.process_commands(commands)

    actions = initial_payload.get("actions")
    runner.action_store.reload_from_dicts(actions or [])


class BaseRunner(object):
    """ Base runner class
    """


class Runner(BaseRunner):
    """ Main runner class

    Its job is to be the orchestrator and receiver for application communication
    It interacts with the backend through session, call heartbeat himself,
    execute commands and forward events
    """

    # Heartbeat delay is 5 minutes by default
    HEARTBEAT_DELAY = 300

    def __init__(
        self,
        queue,
        observation_queue,
        session,
        deliverer,
        remote_command,
        runtime_infos,
        instrumentation,
        action_store,
        metrics_store,
        settings,
        initial_features=None,
        performance_metrics=True,
        tracing_sampler=None,
        interface_manager=None,
        reactive=None,
    ):
        self.logger = logging.getLogger(
            "{}.{}".format(self.__module__, self.__class__.__name__)
        )
        self.queue = queue
        self.observation_queue = observation_queue
        self.deliverer = deliverer
        self.remote_command = remote_command
        self.runtime_infos = runtime_infos
        self.instrumentation = instrumentation
        self.action_store = action_store
        self.metrics_store = metrics_store
        self.settings = settings
        self.stop = False
        # Used to globally disable performance metrics in the agent from the daemon
        self.performance_metrics = performance_metrics
        self.tracing_sampler = tracing_sampler
        self.interface_manager = interface_manager
        self.reactive = reactive

        # Save the time runner started for checking warmup period termination
        self.started = time()

        if initial_features is None:
            initial_features = {}

        # The first time we shouldn't wait too long before sending heartbeat
        self.heartbeat_delay = initial_features.get(
            "heartbeat_delay", self.HEARTBEAT_DELAY
        )

        self.set_call_counts_metrics_period(
            initial_features.get("call_counts_metrics_period", 60)
        )

        self.set_performance_metrics_settings(
            PerformanceMetricsSettings.from_features(initial_features)
        )

        self.set_event_manager_metrics_period(
            initial_features.get("event_manager_metrics_period", 60)
        )

        self.budget = None

        self.set_whitelisted_metric(initial_features.get("whitelisted_metric", True))

        self.last_heartbeat_request = 0

        self.session = session

        # Features
        self.logger.debug("Initial features %s", self.features_get())

        # Next things to send on next heartbeat
        self.next_commands_results = {}

    def run(self):
        """ Infinite loop
        """
        self.logger.debug("Starting the runner")
        while self.stop is False:
            self.run_once()
        self.logger.debug("Exiting the runner now")

    def handle_messages(self, block=True):
        """ Tries to pop and handle most messages before the heartbeat delay
        """
        timeout = self.heartbeat_delay
        deadline = time() + timeout
        while timeout > 0:
            try:
                event = self.queue.get(timeout=timeout, block=block)
                self.handle_message(event)
                self.queue.task_done()
                # Exit now if should stop
                if self.stop:
                    return
            except Empty:
                # timeout exceeded or not blocking
                break
            finally:
                # Tick the deliverer to publish batch if necessary
                self.deliverer.tick()

            # Compute remaining time
            timeout = deadline - time()

    def run_once(self):
        """ Tries to handle most messages and send an heartbeat after a given delay
        """
        self.handle_messages(block=True)
        if self.stop:
            return
        self.logger.debug("Heartbeat after %ss delay", self.heartbeat_delay)
        # Aggregate observations in transit in observations queue
        self.aggregate_observations()
        # Publish the metrics if signals are enabled otherwise they are
        # sent as part of the heartbeat
        if self.session.use_signals:
            self.publish_metrics(force_finalize=False)
        # Always finish with an heartbeat
        self.do_heartbeat()

    def handle_message(self, event):
        """ Handle incoming message
        Process RunnerStop message or pass event to the deliverer
        """
        if event is RunnerStop:
            self.logger.debug("RunnerStop found, logout")
            self.logout()
        elif event is MetricsEvent:
            self.aggregate_observations()
        else:
            self.logger.debug("Handle event: %r", event)
            self.deliverer.post_event(event)

    def process_commands(self, commands):
        """ handle commands
        """
        result = self.remote_command.process_list(commands, self)
        self.next_commands_results.update(result)

    def do_heartbeat(self):
        """ Do an heartbeat, publish finished metrics from MetricsStore and
        past commands results
        """
        payload = {
            "command_results": self.next_commands_results,
        }
        if not self.session.use_signals:
            metrics = self.metrics_store.get_data_to_publish(
                now(), force_finalize=False)
            payload["metrics"] = [
                {k: v for k, v in metric.items() if k in ("name", "observation", "start", "finish")}
                for metric in metrics
            ]

        res = self.session.heartbeat(payload)
        self.last_heartbeat_request = time()

        # Clean sent command results
        self.next_commands_results = {}

        if res is not None:
            self.process_commands(res["commands"])

    def aggregate_observations(self):
        """ Empty the observation queue and update the metric store
        with the observations in the queue.
        """
        unregistered_metrics = set()
        try:
            while True:
                try:
                    name, at, key, value = self.observation_queue.get_nowait()
                    self.metrics_store.update(name, at, key, value)
                except UnregisteredMetric:
                    unregistered_metrics.add(name)
        except Empty:
            pass

        if self.event_manager_metrics_period:
            at = now()
            try:
                for name, item_at, key, value in itertools.chain(
                        self.queue.get_metrics(at=at),
                        self.observation_queue.get_metrics(at=at),
                        self.session.get_metrics(at=at)):
                    if value:
                        self.metrics_store.update(name, item_at, key, value)
            except UnregisteredMetric:
                unregistered_metrics.add(name)

        if unregistered_metrics:
            # metrics could be have been queued before
            # they were disabled by a feature change
            LOGGER.debug("Observations for unregistered metrics: %s",
                         ", ".join(unregistered_metrics))

    def publish_metrics(self, force_finalize=True):
        """ Publish finished metrics from MetricsStore
        """
        metrics = self.metrics_store.get_data_to_publish(
            now(), force_finalize=force_finalize)
        if metrics:
            self.deliverer.post_metrics(metrics)

    def logout(self):
        """ Run cleanup
        """
        self.logger.debug("Logout")

        # Flush metrics
        self.aggregate_observations()
        self.publish_metrics()

        # Drain deliverer
        self.deliverer.drain(resiliently=False)

        self.session.logout()

        # Mark itself as stopped if it's not the end of the application
        self.stop = True

    ###
    # Features
    ###

    def features_get(self):
        """ Returns the current values for all features switches
        """
        res = {
            "heartbeat_delay": self.heartbeat_delay,
            "batch_size": self.deliverer.batch_size,
            "use_signals": self.session.use_signals,
            "max_staleness": self.deliverer.original_max_staleness,
            "call_counts_metrics_period": self.metrics_store.get_metric_period(
                "sqreen_call_counts"
            ),
            "whitelisted_metric": self.whitelisted_metric,
            "event_manager_metrics_period": self.event_manager_metrics_period,
        }
        res.update(self.performance_metrics_settings.as_features())
        return res

    def set_heartbeat_delay(self, heartbeat_delay):
        """ Update the heartbeat delay
        """
        self.heartbeat_delay = heartbeat_delay

    def set_performance_cap_budget(self, budget):
        """ Update the budget of the performance cap feature.
        """
        if budget is not None and budget <= 0:
            raise ValueError("Expected a positive floating number %s" % budget)

        if budget is not None and self.performance_metrics_settings.enabled():
            LOGGER.info("Updated performance cap budget to %0.2fms", budget)
            self.metrics_store.register_metric_definition(
                "request_overbudget_cb", "Sum",
                self.performance_metrics_settings.overtime_period
            )
            self.budget = budget
        else:
            LOGGER.info("Disabled performance cap")
            self.metrics_store.unregister_metric_definition("request_overbudget_cb")
            self.budget = None

    def set_performance_metrics_settings(self, new_perf_met_set):
        self.performance_metrics_settings = new_perf_met_set
        if self.performance_metrics is not True:
            return
        if self.performance_metrics_settings.enabled():
            LOGGER.info("Updated performance monitoring settings")
            self.metrics_store.register_metric_definition(
                "req", "Binning", self.performance_metrics_settings.period,
                base=self.performance_metrics_settings.base,
                unit=self.performance_metrics_settings.unit
            )
            self.metrics_store.register_metric_definition(
                "sq", "Binning", self.performance_metrics_settings.period,
                base=self.performance_metrics_settings.base,
                unit=self.performance_metrics_settings.unit
            )
            self.metrics_store.register_metric_definition(
                "pct", "Binning", self.performance_metrics_settings.period,
                base=self.performance_metrics_settings.pct_base,
                unit=self.performance_metrics_settings.pct_unit
            )
            self.metrics_store.register_metric_definition(
                "sq.*", "Binning",
                self.performance_metrics_settings.period,
                base=self.performance_metrics_settings.base,
                unit=self.performance_metrics_settings.unit
            )
        else:
            LOGGER.info("Disabled performance monitoring")
            self.metrics_store.unregister_metric_definition("req")
            self.metrics_store.unregister_metric_definition("sq")
            self.metrics_store.unregister_metric_definition("pct")
            self.metrics_store.unregister_metric_definition("sq.*")

    def set_call_counts_metrics_period(self, call_counts_metrics_period):
        self.metrics_store.register_metric_definition(
            "sqreen_call_counts", "Sum", call_counts_metrics_period
        )

    def set_whitelisted_metric(self, enabled):
        self.whitelisted_metric = enabled
        if enabled:
            self.metrics_store.register_metric_definition("whitelisted", "Sum", 60)
        else:
            self.metrics_store.unregister_metric_definition("whitelisted")

    def set_event_manager_metrics_period(self, period):
        self.event_manager_metrics_period = period
        if period > 0:
            self.metrics_store.register_metric_definition("event_manager", "Sum", period)
        else:
            self.metrics_store.unregister_metric_definition("event_manager")

    def set_deliverer(self, batch_size, max_staleness):
        # Drain current deliverer
        self.deliverer.drain(resiliently=True)

        # Replace current deliverer
        self.deliverer = get_deliverer(batch_size, max_staleness, self.session)

    def set_ips_whitelist(self, addresses):
        """ Update current RunnerSettings ips_whitelist
        """
        self.logger.debug("Set IPs whitelist on settings %r", self.settings)
        self.settings.set_ips_whitelist(addresses)

    def set_paths_whitelist(self, paths):
        """ Update current RunnerSettings paths_whitelist
        """
        self.logger.debug("Set paths whitelist on settings %r", self.settings)
        self.settings.set_paths_whitelist(paths)

    def set_tracing_configuration(self, tracing_identifier_prefix, scope_definition):
        """ Update the tracing configuration
        """
        self.logger.debug("Set the tracing identifier prefix to %r", tracing_identifier_prefix)
        self.settings.set_tracing_identifier_prefix(tracing_identifier_prefix)
        if self.tracing_sampler is None:
            self.logger.debug("Creating a new tracing sampler with scope definition %r", scope_definition)
            self.tracing_sampler = TracingSampler(scope_definition)
        else:
            self.logger.debug("Updating tracing sampler scope definition %r", scope_definition)
            self.tracing_sampler.update_scope_definition(scope_definition)
