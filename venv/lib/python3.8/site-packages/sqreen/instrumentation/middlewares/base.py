# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base middleware for peripheric frameworks integration
"""
import logging

from ...exceptions import ActionBlock, ActionRedirect, AttackBlocked
from ..hook_point import (
    execute_failing_callbacks,
    execute_post_callbacks,
    execute_pre_callbacks,
)

LOGGER = logging.getLogger(__name__)

VALID_ACTIONS_PRE = ("raise", "action_block", "action_redirect", "modify_args",)
VALID_ACTIONS_POST = ("raise", "override",)
VALID_ACTIONS_FAILING = ("override",)


class BaseMiddleware(object):
    """ Middleware base class for frameworks middleware hooks
    """

    def __init__(self, strategy):
        self.strategy = strategy

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, repr(self.strategy))

    def create_transaction(self):
        return self.strategy.settings.get_callbacks(self.strategy.strategy_id), {}

    def execute_pre_callbacks(self, transaction, args, record_attack=True):
        """ Execute pre callbacks. Only process valid action, in this context it's raising.
        """
        callbacks, options = transaction
        action = execute_pre_callbacks(
            self.strategy.strategy_id, callbacks["pre"], self, args, dict(), options,
            valid_actions=VALID_ACTIONS_PRE,
        )
        action_status = action.get("status")
        if action_status is None:
            pass
        elif action_status == "modify_args":
            return action.get("args")[0]
        elif action_status == "raise" and record_attack:
            LOGGER.debug(
                "Callback %s detected an attack", action.get("rule_name")
            )
            raise AttackBlocked(action.get("rule_name"))
        elif action_status == "action_block" and record_attack:
            LOGGER.debug(
                "Action %s blocked the request", action.get("action_id")
            )
            raise ActionBlock(action.get("action_id"))
        elif action_status == "action_redirect" and record_attack:
            LOGGER.debug(
                "Action %s redirected the request to %r",
                action.get("action_id"),
                action["target_url"],
            )
            raise ActionRedirect(action.get("action_id"), action["target_url"])
        return args

    def execute_post_callbacks(self, transaction, response, args=(), record_attack=True):
        """ Execute post callbacks. Only process valid action, in this context it's raising.
        """
        callbacks, options = transaction
        options["result"] = response
        action = execute_post_callbacks(
            self.strategy.strategy_id,
            callbacks["post"],
            self, args, dict(), options,
            valid_actions=VALID_ACTIONS_POST,
        )

        action_status = action.get("status")

        if action_status is None:
            pass
        elif action_status == "override":
            return action.get("new_return_value")
        elif action_status == "raise" and record_attack:
            LOGGER.debug(
                "Callback %s detected an attack", action.get("rule_name")
            )
            raise AttackBlocked(action.get("rule_name"))

        return response

    def execute_failing_callbacks(self, transaction, exception, args=()):
        """ Execute failing callbacks. Only process valid action, in this context it's None.
        """
        callbacks, options = transaction
        if isinstance(exception, Exception):
            exception = (exception.__class__, exception, None)
        options["exc_info"] = exception
        action = execute_failing_callbacks(
            self.strategy.strategy_id,
            callbacks["failing"],
            self, args, dict(), options,
            valid_actions=VALID_ACTIONS_FAILING,
        )

        action_status = action.get("status")
        if action_status is not None and action_status == "override":
            return action.get("new_return_value")
