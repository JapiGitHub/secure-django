# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Track login/signup events
"""
import logging

from ..rules import RuleCallback
from ..rules_actions import RecordSDKEventMixin
from ..utils import now
from .matcher_callback import MatcherRule

LOGGER = logging.getLogger(__name__)


class SDKTrackEvent(RecordSDKEventMixin, RuleCallback):

    INTERRUPTIBLE = False

    def pre(self, instance, args, kwargs, options):
        self.record_sdk_event(*args, **kwargs)


class IdentifyMixin:

    def identify(self, user_identifiers, traits={}):
        self.storage.update_request_store(user_identifiers=user_identifiers)
        self.storage.observe(
            "sdk", ["identify", now(), user_identifiers, traits],
            report=False
        )


class SDKIdentify(IdentifyMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        """Associate the current request with a user."""
        traits = kwargs.get("traits") or {}
        user_identifiers = dict(kwargs.get("user_identifiers", {}))
        if args:
            user_identifiers.update(args[0])
        self.identify(user_identifiers, traits)


class DjangoAuthTrack(IdentifyMixin, RecordSDKEventMixin, MatcherRule):

    INTERRUPTIBLE = False

    source = "auth_track"

    def post(self, instance, args, kwargs, options):
        # Django authentication model return either an User or None
        success = options.get("result") is not None

        # Search for credentials identifier that match the whitelist
        identifiers = {k: v for k, v in kwargs.items()
                       if self.match(k) and v is not None}
        if identifiers:
            self.record_sdk_event(
                "sq.sdk.users.login",
                {"properties": {"success": success}, "user_identifiers": identifiers}
            )
            if success:
                self.identify(identifiers)


class SDKAuthTrack(IdentifyMixin, RecordSDKEventMixin, RuleCallback):

    INTERRUPTIBLE = False

    source = "auth_track"

    def pre(self, instance, args, kwargs, options):
        """Report a metric for SDK authentication tracking."""

        def _extract(success, **user_identifiers):
            return success, user_identifiers

        success, identifiers = _extract(*args, **kwargs)

        if identifiers:
            self.record_sdk_event(
                "sq.sdk.users.login",
                {"properties": {"success": success}, "user_identifiers": identifiers}
            )
            if success:
                self.identify(identifiers)


class SDKSignupTrack(IdentifyMixin, RecordSDKEventMixin, RuleCallback):

    INTERRUPTIBLE = False

    source = "signup_track"

    def pre(self, instance, args, kwargs, options):
        """Report a metric for SDK signup tracking."""
        if kwargs:
            self.record_sdk_event(
                "sq.sdk.users.signup",
                {"user_identifiers": kwargs}
            )
            self.identify(kwargs)
