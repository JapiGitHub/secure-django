# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Asynchronous variant of hook_point."""

import logging
import sys

from .._vendors.wrapt import FunctionWrapper
from ..exceptions import ActionBlock, ActionRedirect, AttackBlocked
from .hook_point import (
    execute_failing_callbacks,
    execute_post_callbacks,
    execute_pre_callbacks,
)

LOGGER = logging.getLogger(__name__)


def async_hook_point(strategy, hook_name, hook_method, original):
    """Asynchronous variant of hook_point."""
    from asyncio import coroutine

    @coroutine
    def wrapper(wrapped, instance, args, kwargs):
        LOGGER.debug(
            "Checking before async hook point of %s for %s/%s",
            strategy,
            hook_name,
            hook_method,
        )
        strategy.before_hook_point()
        key = (hook_name, hook_method)
        callbacks = strategy.settings.get_callbacks(key)
        options = {}

        # Call pre callbacks.
        action = execute_pre_callbacks(key, callbacks["pre"], instance, args, kwargs, options)

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

        # Call the original method.
        retry = True
        while retry is True:
            try:
                retry = False
                # Try to call the original coroutine.
                result = yield from wrapped(*args, **kwargs)
            except Exception:
                # Either raise an exception, set a return value or retry.
                options["exc_info"] = sys.exc_info()
                action = execute_failing_callbacks(
                    key, callbacks["failing"], instance, args, kwargs, options
                )

                status = action.get("status")
                if status is None:
                    pass
                elif status == "override":
                    return action.get("new_return_value")
                elif status == "retry":
                    retry = True
                elif status == "raise":
                    LOGGER.debug(
                        "Callback %s detected an attack",
                        action.get("rule_name"),
                    )
                    raise AttackBlocked(action.get("rule_name"))

                # Be sure to raise if no retry or override.
                if retry is False:
                    raise

        # Then call post callback in reverse order to simulate decorator
        # behavior.
        options["result"] = result
        action = execute_post_callbacks(
            key, callbacks["post"], instance, args, kwargs, options
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

        # Return the original value.
        return result

    return FunctionWrapper(original, wrapper)
