# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Contains the hook_point, the code actually executed in place of
application code
"""
import logging
import sys

from .._vendors.wrapt import FunctionWrapper
from ..exceptions import ActionBlock, ActionRedirect, AttackBlocked
from ..execute_callbacks import execute_callbacks
from ..runtime_storage import runtime
from .helpers import guard_call

LOGGER = logging.getLogger(__name__)


# Order of valid actions is important, if multiple actions are returned on the
# same hookpoint, the smallest index wins.
VALID_ACTIONS_PRE = (
    "raise",
    "action_block",
    "action_redirect",
    "override",
    "modify_args",
)

VALID_ACTIONS_FAILING = (
    "raise",
    "retry",
    "override",
)

VALID_ACTIONS_POST = (
    "raise",
    "override"
)


def execute_pre_callbacks(
    key, callbacks, instance, args, kwargs, options, storage=runtime,
    override_budget=None, valid_actions=VALID_ACTIONS_PRE,
):
    """ Execute pre_callbacks. Pre callbacks will receive these arguments:
    (instance, args, kwargs)
    """
    if callbacks:
        return guard_call(
            key,
            execute_callbacks,
            callbacks,
            "pre",
            instance,
            args,
            kwargs,
            options,
            storage=storage,
            override_budget=override_budget,
            valid_actions=valid_actions,
        )
    return {}


def execute_failing_callbacks(
    key, callbacks, instance, args, kwargs, options, storage=runtime,
    override_budget=None, valid_actions=VALID_ACTIONS_FAILING,
):
    """ Execute failing_callbacks. Failing callbacks will receive these arguments:
    (instance, args, kwargs, options)
    """
    if callbacks:
        return guard_call(
            key,
            execute_callbacks,
            reversed(callbacks),
            "failing",
            instance,
            args,
            kwargs,
            options,
            storage=storage,
            override_budget=override_budget,
            valid_actions=valid_actions,
        )
    return {}


def execute_post_callbacks(
    key, callbacks, instance, args, kwargs, options, storage=runtime,
    override_budget=None, valid_actions=VALID_ACTIONS_POST,
):
    """ Execute post_callbacks. Post callbacks will receive these arguments:
    (instance, args, kwargs, options)
    """
    if callbacks:
        return guard_call(
            key,
            execute_callbacks,
            reversed(callbacks),
            "post",
            instance,
            args,
            kwargs,
            options,
            storage=storage,
            override_budget=override_budget,
            valid_actions=valid_actions,
        )
    return {}


def hook_point_wrapper(strategy, hook_name, hook_method, storage=runtime):
    """ Execute the original method and pre/post/failing callbacks
    """
    key = (hook_name, hook_method)

    def wrapper(wrapped, instance, args, kwargs):
        strategy.before_hook_point()
        callbacks = strategy.settings.get_callbacks(key)
        options = {}

        # Call pre callbacks
        action = execute_pre_callbacks(
            key,
            callbacks["pre"],
            instance,
            args,
            kwargs,
            options,
            storage=storage
        )

        status = action.get("status")
        if status is None:
            pass
        elif status == "modify_args":
            args, kwargs = action["args"]
        elif status == "override":
            return action.get("new_return_value")
        elif status == "raise":
            LOGGER.debug(
                "Callback %s detected an attack", action.get("rule_name")
            )
            raise AttackBlocked(action.get("rule_name"))
        elif status == "action_block":
            LOGGER.debug(
                "Action %s blocked the request", action.get("action_id")
            )
            raise ActionBlock(action.get("action_id"))
        elif status == "action_redirect":
            LOGGER.debug(
                "Action %s redirected the request to %r",
                action.get("action_id"),
                action["target_url"],
            )
            raise ActionRedirect(action.get("action_id"), action["target_url"])

        # Call original method
        retry = True
        result = None
        while retry is True:
            try:
                retry = False
                # Try to call original function
                result = wrapped(*args, **kwargs)
            except Exception:
                # In case of error, call fail callbacks with exception infos
                options["exc_info"] = sys.exc_info()

                # Either raise an exception, set a return value or retry
                action = execute_failing_callbacks(
                    key, callbacks["failing"], instance, args, kwargs,
                    options, storage=storage
                )

                status = action.get("status")
                if status is None:
                    pass
                elif status == "override":
                    return action.get("new_return_value")
                elif status == "raise":
                    LOGGER.debug(
                        "Callback %s detected an attack",
                        action.get("rule_name"),
                    )
                    raise AttackBlocked(action.get("rule_name"))
                elif status == "retry":
                    retry = True

                # Be sure to raise if no retry or override
                if retry is False:
                    raise

        # Then call post callback in reverse order to simulate decorator
        # behavior
        options["result"] = result
        action = execute_post_callbacks(
            key, callbacks["post"], instance, args, kwargs,
            options, storage=storage,
        )

        status = action.get("status")
        if status is None:
            pass
        elif status == "override":
            return action.get("new_return_value")
        elif status == "raise":
            LOGGER.debug(
                "Callback %s detected an attack", action.get("rule_name")
            )
            raise AttackBlocked(action.get("rule_name"))

        # And return the original value
        return result
    return wrapper


def hook_point(strategy, hook_name, hook_method, original, storage=runtime):
    wrapper = hook_point_wrapper(strategy, hook_name, hook_method, storage)
    return FunctionWrapper(original, wrapper)
