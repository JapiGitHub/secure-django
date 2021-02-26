# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Collect and aggregate metrics
"""
import fnmatch
import math
import re
from collections import Counter, defaultdict, namedtuple
from datetime import timedelta
from logging import getLogger

from .exceptions import SqreenException
from .utils import itervalues, truncate_time

LOGGER = getLogger(__name__)


class BaseAggregator(object):
    """ Base classes for aggregators.

    It contains the methods to update a period with new data and finalize the
    data just before uploading.
    Aggregators don't store any state, it creates, updates, and finizalises
    an accumulator that is passed by the MetricsStore.
    """

    name = "Base"

    @staticmethod
    def default_value_factory():
        return None

    @classmethod
    def initialize(cls, **options):
        """ Initialize the accumulator.
        """
        return defaultdict(cls.default_value_factory)

    @staticmethod
    def is_empty(accumulator):
        return len(accumulator) == 0

    @classmethod
    def update(cls, key, value, accumulator):
        """ Update the accumulator for the period. For updating only the key,
        override update_key instead.
        """
        accumulator[key] = cls.update_key(value, accumulator[key])
        return accumulator

    @staticmethod
    def update_key(new_value, cur_value):
        """ Update the data for a key in the period. For updating the whole data,
        override update instead.
        """
        raise NotImplementedError("")

    @classmethod
    def finalize(cls, accumulator):
        """ Finalize the period, by default return the data. Could be override
        to compute a ration or sum some elements.
        """
        return accumulator


class CollectAggregator(BaseAggregator):
    """ Simple aggregator that stores all the observations points,
    used in tests mostly
    """

    name = "Collect"
    default_value_factory = list

    @staticmethod
    def update_key(new_value, cur_value):
        cur_value.append(new_value)
        return cur_value


class SumAggregator(BaseAggregator):

    name = "Sum"
    default_value_factory = int

    @staticmethod
    def update_key(new_value, cur_value):
        return cur_value + new_value


class ExtensionPerformanceMetricAggregator(BaseAggregator):

    name = "ExtensionPerformance"

    @classmethod
    def initialize(cls, **options):
        return {'v': Counter()}

    @staticmethod
    def is_empty(accumulator):
        return len(accumulator["v"]) == 0

    @classmethod
    def update(cls, key, value, accumulator):
        """ Ignore key
        """
        accumulator['u'] = value['u']
        accumulator['b'] = value['b']
        accumulator['v'].update(value['v'])
        return accumulator


class AverageAggregator(BaseAggregator):

    name = "Average"

    @staticmethod
    def default_value_factory():
        return {"sum": 0, "count": 0}

    @staticmethod
    def update_key(new_value, cur_value):
        cur_value["sum"] += new_value
        cur_value["count"] += 1
        return cur_value

    @classmethod
    def finalize(cls, accumulator):
        final_data = {}

        for key, value in accumulator.items():
            final_data[key] = value["sum"] / float(value["count"])

        return final_data


BinningAccumulator = namedtuple("BinningAccumulator", [
    "unit", "base", "inv_log_base", "sub_parcel", "values"
])


class BinningAggregator(BaseAggregator):
    """Sample numbers into logarithmic bins."""

    name = "Binning"

    @classmethod
    def initialize(cls, **options):
        unit = options.get("unit")
        base = options.get("base")
        if unit is None or not unit > 0.0:
            raise InvalidOptionAggregator("unit must be a positive value")
        if base is None or not base > 1.0:
            raise InvalidOptionAggregator("base must be greater than 1.0")
        log_base = math.log(base)
        log_unit = math.log(unit)
        return BinningAccumulator(unit, base, 1 / log_base, log_unit / log_base, Counter())

    @staticmethod
    def is_empty(accumulator):
        return len(accumulator.values) == 0

    @classmethod
    def update(cls, key, value, accumulator):
        # key is ignored
        if value < accumulator.unit:
            value_bin = 1
        else:
            value_bin = 2 + int(math.floor(math.log(value) * accumulator.inv_log_base
                                - accumulator.sub_parcel))
        accumulator.values[value_bin] += 1
        accumulator.values["max"] = max(accumulator.values["max"], value)
        return accumulator

    @classmethod
    def finalize(cls, accumulator):
        return {
            "u": accumulator.unit,
            "b": accumulator.base,
            "v": dict(accumulator.values.items()),
        }


class InvalidOptionAggregator(SqreenException):
    """ Exception raised when an invalid option was passed to an aggregator.
    """


class UnknownAggregator(SqreenException):
    """ Exception raised when trying to register a metric with an unknown
    aggregation kind
    """


class AlreadyRegisteredMetric(SqreenException):
    """ Exception raised when trying to register twice the same metric
    name.
    """


class AlreadyRegisteredAggregator(SqreenException):
    """ Exception raised when trying to register twice the same aggregator
    name.
    """


class UnregisteredMetric(SqreenException):
    """ Exception raised when trying to update an unregistered metric.
    """


PRODUCTION_AGGREGATORS = [SumAggregator(),
                          AverageAggregator(),
                          ExtensionPerformanceMetricAggregator(),
                          BinningAggregator()]


class MetricsStore(object):
    """ Store the dict of currently monitored metrics.

    For each metric, store a dict containing:
    - The start time of monitored period.
    - The maximum period time.
    - The kind of aggregator.
    - The aggregated data, the value is managed by the aggregator directly.

    Store also the list of available aggregator indexed by a kind.

    When periods are finished, store them to be retrieved for pushing in
    the store attribute.
    """

    def __init__(self):
        self.store = []
        self.metrics = {}
        self.aggregators = {}
        self.definitions = {}

    def _register_metric(self, name, kind, period, **options):
        """ Register a new metric
        """
        if name in self.metrics:
            LOGGER.debug("Update existing metric %r", name)

            existing_metric = self.metrics[name]
            saved_metric_kind = existing_metric["kind"]
            if saved_metric_kind != kind:
                raise AlreadyRegisteredMetric(
                    "Metric {!r} has already been registered with kind {}"
                    .format(name, saved_metric_kind)
                )

            # Update the period
            existing_metric["period"] = period
            # Reset the metric if the options have changed
            if options != existing_metric["options"]:
                existing_metric["options"] = options
                self.metrics[name] = self.reset_metric(existing_metric)
        else:
            LOGGER.debug("Creating new metric %r", name)

            if kind not in self.aggregators:
                raise UnknownAggregator(
                    "Unknown aggregation kind: {}".format(kind)
                )
            metric = self._new_metric(kind, period, options)
            self.metrics[name] = self.reset_metric(metric)

    def register_metric_definition(self, name, kind, period, **options):
        """ Register a new metric definition
        """
        if "*" in name:
            LOGGER.debug("Register metric definition %r", name)
            re_pattern = re.compile(fnmatch.translate(name))
            for existing_name in list(self.metrics.keys()):
                if re_pattern.match(existing_name):
                    self._register_metric(existing_name, kind, period, **options)
            if kind not in self.aggregators:
                raise UnknownAggregator(
                    "Unknown aggregation kind: {}".format(kind)
                )
            self.definitions[name] = (re_pattern, kind, period, options)
        else:
            self._register_metric(name, kind, period, **options)

    def unregister_metric_definition(self, name):
        """ Unregister a metric definition
        """
        if "*" in name:
            LOGGER.debug("Unregister metric definition %r", name)

            definition = self.definitions.pop(name, None)
            if definition is not None:
                for existing_name in list(self.metrics.keys()):
                    if definition[0].match(existing_name):
                        LOGGER.debug("Unregister metric %r", existing_name)
                        self.metrics.pop(existing_name, None)
        else:
            LOGGER.debug("Unregister metric %r", name)
            self.metrics.pop(name, None)

    def ensure_ext_perf_metric(self, name, period):
        if name in self.metrics:
            return

        self._register_metric(name, 'ExtensionPerformance', period)

    @staticmethod
    def _new_metric(kind, period, options):
        """ Return a dict for an empty metric period
        """
        return {
            "kind": kind,
            "period": period,
            "observation": None,
            "start": None,
            "options": options,
        }

    def register_aggregator(self, name, aggregator_function):
        """ Register a new aggregator under the name passed in input
        """
        if name in self.aggregators:
            msg = "Aggregator '{}' has already been registered to: {}"
            raise AlreadyRegisteredAggregator(
                msg.format(name, self.aggregators[name])
            )
        self.aggregators[name] = aggregator_function

    def register_production_aggregators(self):
        """ Register production aggregators
        """
        for aggregator in PRODUCTION_AGGREGATORS:
            self.register_aggregator(aggregator.name, aggregator)

    def _new_metric_for_definition(self, name, at=None):
        """ Create a new metric if it matches a metric definition.
        """
        for pattern, kind, period, options in itervalues(self.definitions):
            if pattern.match(name):
                metric = self._new_metric(kind, period, options)
                self.metrics[name] = self.reset_metric(metric, at)
                return metric

    def update(self, name, at, key, value):
        """ Logic behind metric updating.

        Check if the start time is set for the metric period.
        Check if the metric period has expired, if so save it and create
        a blank metric period.
        Then call the aggregator to compute the new data
        """
        try:
            metric = self.metrics[name]
        except KeyError:
            metric = self._new_metric_for_definition(name, at=at)
            if metric is None:
                raise UnregisteredMetric("Unknown metric {!r}".format(name))

        # Check if the metric should be published or not
        metric = self.check_metric_period_over(metric, name, at, False)
        # Update start time if not set already (registered but never updated)
        if metric["start"] is None:
            metric["start"] = truncate_time(at, round_to=metric["period"])
        self._update_metric(metric, key, value)

    def _update_metric(self, metric, key, value):
        """ Actual method that call the aggregator to compute the new data.
        """
        aggregator = self.aggregators[metric["kind"]]

        # Compute the new value
        new_data = aggregator.update(key, value, metric["observation"])
        metric["observation"] = new_data

    def check_metric_period_over(self, metric, name, at, force_finalize=True):
        """ Check a single metric to see if its period is over, if so
        finalize it and returns the new one.
        If force_finalize if False, check that the metric period is over first.
        """
        if metric["start"] is None:
            return metric

        period_over = (
            metric["start"] + timedelta(seconds=metric["period"]) < at
        )
        if force_finalize or period_over:
            return self.finalize_period(metric, name, at)

        return metric

    def check_all_metrics_period_over(self, at, force_finalize=True):
        """ Check all registered metrics to see if their period are over, if so
        finalize them.
        If force_finalize if False, check that the metric period is over first.
        """
        for metric_name, metric in self.metrics.items():
            self.check_metric_period_over(
                metric, metric_name, at, force_finalize
            )

    def finalize_period(self, metric, name, at):
        """ Finalize a metric period. For each registered metric, call the
        finalize method on correspondent aggregator and instantiate a new blank
        metric period.

        Called if either the period time was crossed or can forced on logout.
        """
        aggregator = self.aggregators[metric["kind"]]
        # If no data has been gathered
        if not aggregator.is_empty(metric["observation"]):
            # Retrieve the current period
            # Call the finalize method on the aggregator

            finished = dict(metric)
            finished["name"] = name
            finished["observation"] = aggregator.finalize(
                metric["observation"]
            )
            usual_finish = metric["start"] + timedelta(seconds=metric["period"])
            finished["finish"] = at if at < usual_finish else usual_finish
            self.store.append(finished)

        # Reset the period
        metric = self.reset_metric(metric, at)
        self.metrics[name] = metric
        return metric

    def reset_metric(self, metric, at=None):
        if at is not None:
            at = truncate_time(at, round_to=metric["period"])
        aggregator = self.aggregators[metric["kind"]]
        metric["observation"] = aggregator.initialize(**metric["options"])
        metric["start"] = at
        return metric

    def get_data_to_publish(self, at, force_finalize=True):
        """ Return the list of finished periods, reset the list of
        finished periods after.
        """
        self.check_all_metrics_period_over(at, force_finalize)

        finished_periods = self.store
        self.store = []
        return finished_periods

    ###
    # Helpers for debug and tests
    ###

    def list_metrics(self):
        """ Return the list of registered metrics
        """
        # The list must be a copy so that we can still register / unregister metrics.
        return list(self.metrics.keys())

    def is_registered(self, name):
        """ Return True if the metric was already registered.
        """
        return name in self.metrics

    def get_metric_kind(self, name):
        """ Return the kind of a given metric
        """
        return self.metrics[name]["kind"]

    def get_metric_period(self, name):
        """ Return the period of a given metric
        """
        return self.metrics[name]["period"]

    def get_metric_start(self, name):
        """ Return the start time for a given metric
        """
        return self.metrics[name]["start"]

    def get_metric_aggregate(self, name):
        """ Return the current aggregated data for a given metric
        """
        return self.metrics[name]["observation"]
