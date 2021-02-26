# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Enforce security responses for SDK users or IP addresses.
"""

import logging

from ..actions import ActionName
from ..binding_accessor import BindingAccessor
from ..rules import RuleCallback
from ..rules_actions import RecordSDKEventMixin

LOGGER = logging.getLogger(__name__)


class SecurityResponsesIP(RecordSDKEventMixin, RuleCallback):

    INTERRUPTIBLE = False

    def pre(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        if request is None or self.runner is None:
            return
        client_ip = request.raw_client_ip
        if client_ip is None:
            return
        action = self.runner.action_store.get_for_ip(client_ip)
        if action is None:
            return
        if action.send_response:
            self.record_sdk_event(
                "sq.action.{}".format(action.name),
                {
                    "properties": {"output": {"ip_address": str(client_ip)}, "action_id": action.iden},
                    "collect_body": True
                }
            )
        if action.name == ActionName.BLOCK_IP:
            LOGGER.debug(
                "IP %s is blacklisted by action %s",
                client_ip,
                action.iden,
            )
            return {
                "status": "action_block",
                "action_id": action.iden,
                "immediate": True,
            }
        elif action.name == ActionName.REDIRECT_IP:
            LOGGER.debug(
                "IP %s is redirected to %r by action %s",
                client_ip,
                action.target_url,
                action.iden,
            )
            return {
                "status": "action_redirect",
                "action_id": action.iden,
                "target_url": action.target_url,
                "immediate": True,
            }


# Compatibility alias
IPActionCB = SecurityResponsesIP


class SecurityResponsesUser(RecordSDKEventMixin, RuleCallback):

    def __init__(self, *args, **kwargs):
        super(SecurityResponsesUser, self).__init__(*args, **kwargs)
        arguments = self.callbacks.get("pre")
        if arguments is not None:
            self._arguments = [BindingAccessor(ba) for ba in arguments]
        else:
            self._arguments = None

    def pre(self, instance, args, kwargs, options):
        """Trigger an action for a user when required."""
        if self.runner is None:
            return

        request = self.storage.get_current_request()
        response = self.storage.get_current_response()

        binding_eval_args = {
            "request": request,
            "response": response,
            "inst": instance,
            "args": self.storage.get_current_args(args),
            "kwargs": kwargs,
            "data": self.data,
        }

        resolved_args = binding_eval_args["args"]
        if self._arguments is not None:
            resolved_args = [
                arg.resolve(**binding_eval_args) for arg in self._arguments]

        if not resolved_args:
            return

        user_dict = resolved_args[0]
        action = self.runner.action_store.get_for_user(user_dict)
        if action is None:  # No action planned for this user, do nothing.
            return
        if action.send_response:
            self.record_sdk_event(
                "sq.action.{}".format(action.name),
                {
                    "properties": {"output": {"user": user_dict}, "action_id": action.iden},
                    "collect_body": True
                }
            )
        if action.name == ActionName.BLOCK_USER:
            LOGGER.debug("User %r is blocked by action %r", user_dict, action.iden)
            return {
                "status": "action_block",
                "action_id": action.iden,
                "immediate": True,
            }
        elif action.name == ActionName.REDIRECT_USER:
            LOGGER.debug(
                "User %r is redirected to %r by action %r",
                user_dict,
                action.target_url,
                action.iden,
            )
            return {
                "status": "action_redirect",
                "action_id": action.iden,
                "target_url": action.target_url,
                "immediate": True,
            }
