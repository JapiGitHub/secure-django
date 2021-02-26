# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Aggregate authentication tentatives
"""
import json
import logging

from ..rules import RuleCallback
from ..rules_actions import RecordObservationMixin
from ..utils import CustomJSONEncoder
from .matcher_callback import MatcherRule

LOGGER = logging.getLogger(__name__)


class AuthMetricsMixin(RecordObservationMixin):

    def record_auth_metrics(self, auth_status, identifiers):
        request = self.storage.get_current_request()
        if not request:
            LOGGER.debug("No request was recorded, abort")
            return

        key = {
            "keys": [(k.lower(), v) for k, v in identifiers.items()],
            "ip": request.client_ip
        }
        observation_key = json.dumps(
            key, separators=(",", ":"), sort_keys=True, cls=CustomJSONEncoder
        )
        self.record_observation(auth_status, observation_key, 1)


class DjangoAuthMetrics(AuthMetricsMixin, MatcherRule):

    INTERRUPTIBLE = False

    def post(self, instance, args, kwargs, options):
        # Django authentication model return either an User or None
        auth_status = "auto-login-fail" if options.get("result") is None else "auto-login-success"

        # Search for credentials identifier that match the whitelist
        identifiers = {k: v for k, v in kwargs.items()
                       if self.match(k) and v is not None}
        if identifiers:
            self.record_auth_metrics(auth_status, identifiers)


# Compatibility callback name
AuthMetricsCB = DjangoAuthMetrics


class SDKAuthMetrics(AuthMetricsMixin, RuleCallback):

    INTERRUPTIBLE = False

    def pre(self, instance, args, kwargs, options):
        """Report a metric for SDK authentication tracking."""

        def _extract(success, **user_identifiers):
            return success, user_identifiers

        success, identifiers = _extract(*args, **kwargs)

        if identifiers:
            auth_status = "sdk-login-success" if success else "sdk-login-fail"
            self.record_auth_metrics(auth_status, identifiers)


class SDKSignupMetrics(AuthMetricsMixin, RuleCallback):

    INTERRUPTIBLE = False

    def pre(self, instance, args, kwargs, options):
        """Report a metric for SDK signup tracking."""
        if kwargs:
            self.record_auth_metrics("sdk-signup", kwargs)
