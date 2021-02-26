# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Let's execute the callbacks.
"""
import logging
import sys
from traceback import extract_stack

from .exceptions import MissingDataException, RequestBlocked, SqreenException
from .remote_exception import RemoteException
from .runtime_storage import runtime
from .utils import Iterable, Mapping

LOGGER = logging.getLogger(__name__)


def _compute_result_action(current_result, next_result, valid_actions):
    """ Compute the next result_action based on current one and the callback
    result
    """
    valid_actions = valid_actions or ()
    current_status = current_result.get("status")
    next_status = next_result.get("status")
    # Check the validity of action per method
    if next_status not in valid_actions:
        # Ignore it
        return current_result

    if current_status not in valid_actions:
        return next_result

    current_result_order = valid_actions.index(current_result.get("status"))
    next_result_order = valid_actions.index(next_result.get("status"))

    # Return the old one only if it has more priority
    if current_result_order < next_result_order:
        return current_result
    else:
        return next_result


def _modify_args(action, args, kwargs):
    """ Return new modified args from action.
    """
    new_args = action.get("args")
    if new_args:
        nargs, nkwargs = new_args
    else:
        nargs = list(args)
        nkwargs = dict(kwargs)

    patch_args = action.pop("patch_args", None)
    if patch_args:
        for key, value in patch_args:
            if isinstance(key, int):
                nargs[key] = value
            else:
                kwargs[key] = value
        # Update the current actions with the new args
        action["args"] = (nargs, nkwargs)

    if not isinstance(nargs, Iterable) or isinstance(nargs, Mapping):
        raise ValueError("Invalid type for args: {!r}".format(nargs))
    if not isinstance(nkwargs, Mapping):
        raise ValueError("Invalid type for kwargs: {!r}".format(nkwargs))
    return nargs, nkwargs


def execute_callback(
    callback, method, instance, result_action, args, kwargs, options,
    storage=runtime, override_budget=None, valid_actions=None
):
    """ Execute a callback protected inside a broad try except.

    The result_action argument is a dict where each callback pushes its results.
    """

    callback_method = getattr(callback, method)

    if callback.collaborative:
        options["__sqreen_override_budget"] = override_budget

    if result_action:
        # Give access to the previous callbacks result action
        # For example, it allows a callback to know if the return value
        # will be overwritten or if the args have been changed
        options["result_action"] = result_action

    try:
        result = callback_method(instance, args, kwargs, options)

        # First process of result
        if not result or not isinstance(result, dict):
            return result_action, args, kwargs

        if not callback.block:
            LOGGER.debug("%s cannot block, ignoring return value", callback)
            return result_action, args, kwargs

        # Set rule_name if not set
        result.setdefault("rule_name", callback.rule_name)

        # We need to process MODIFY_ARGS for next callbacks
        # before setting result_action because we have to check the arguments format
        if result.get("status") == "modify_args":
            args, kwargs = _modify_args(result, args, kwargs)

        result_action = _compute_result_action(
            result_action, result, valid_actions
        )

        return result_action, args, kwargs

    except RequestBlocked:
        if not callback.block:
            LOGGER.debug("%s cannot block, ignoring exception", callback)
            return result_action, args, kwargs
        raise

    except MissingDataException:
        raise

    except Exception as exception:
        LOGGER.debug("An exception occurred while trying to execute %s", callback, exc_info=True)

        exc_info = sys.exc_info()
        current_request = storage.get_current_request()
        stack = extract_stack()

        if current_request:
            callback.record_exception(exception, exc_info, stack)
        else:
            callback_exception_payload = callback.exception_infos()

            # Try to recover some infos from the exception if it's a SqreenException
            exception_infos = {}
            if isinstance(exception, SqreenException):
                exception_infos.update(exception.exception_infos())  # pylint: disable=no-member

            remote_exception = RemoteException.from_exc_info(
                exc_info,
                callback_payload=callback_exception_payload,
                exception_payload=exception_infos,
                stack=stack,
            )
            callback.runner.queue.put(remote_exception)

        return result_action, args, kwargs


def execute_callbacks(
    callbacks, method, instance, args, kwargs, options,
    storage=runtime, override_budget=None, valid_actions=None
):
    """ Execute a list of callbacks method (pre/post/fail), catch any exception
    that could happens.

    Aggregate the callbacks result (format {"status": COMMAND}), compute the
    final ACTION to execute and return it.
    For every ACTION, each callback is executed even if the first callback
    detected an attack except specified otherwise with the "immediate" key.

    The performance cap budget can be ignored by the caller by specifying an
    `override_budget` value though it is currently only used by the PHP daemon.
    """
    result_action = {}
    # Test if override_budget is already negative
    overtime = override_budget <= 0 if override_budget is not None else None
    total_duration = 0
    budget = None

    # Execute the callbacks
    for callback in callbacks:

        if callback.whitelisted:
            continue

        # Budget must be updated before executing the first callback
        if overtime is None and budget is None:
            budget = override_budget or callback.get_remaining_budget()
            overtime = budget <= 0 if budget is not None else False

        # Budget is exhausted, skip the callback if possible
        if overtime and callback.skippable:
            callback.record_overtime(lifecycle=method)
            continue

        with storage.trace() as callback_trace:
            result = execute_callback(
                callback, method, instance, result_action, args, kwargs, options,
                storage=storage, override_budget=budget, valid_actions=valid_actions
            )

        result_action, args, kwargs = result

        total_duration += callback_trace.duration_ms
        if budget is not None:
            budget -= callback_trace.duration_ms
            overtime = budget <= 0
            if overtime:
                callback.record_overtime(lifecycle=method)

        if result_action.get("immediate", False):
            # Stop execution of other callbacks on this hook point if the result must be immediate.
            break

    # It is either empty dict if no override or the last one
    return result_action
