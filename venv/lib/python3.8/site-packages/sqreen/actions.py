# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Actions for security responses."""

import logging
from collections import defaultdict
from time import time

from .ip_radix import Radix

LOGGER = logging.getLogger(__name__)


class ActionName(object):
    """Enumeration of action names."""

    BLOCK_IP = "block_ip"
    REDIRECT_IP = "redirect_ip"
    BLOCK_USER = "block_user"
    REDIRECT_USER = "redirect_user"


_AVAILABLE_ACTIONS = {}


def register_action(name):
    """Decorator function to register an action."""

    def decorator(action_cls):
        _AVAILABLE_ACTIONS[name] = action_cls
        action_cls.name = name
        return action_cls

    return decorator


class BaseAction(object):
    """Base class for actions."""

    name = None

    def __init__(self, iden, params, duration=None, send_response=True):
        self.iden = iden
        self.params = params
        self.duration = duration
        if duration is not None:
            self.timeout = time() + duration
        else:
            self.timeout = None
        self.send_response = send_response

    def __repr__(self):
        return "{}({!r}, {!r}, {!r}, {!r})".format(
            self.__class__.__name__,
            self.iden,
            self.params,
            self.duration,
            self.send_response,
        )

    def to_dict(self):
        """Convert the action into a dict."""
        return {
            "action": self.name,
            "action_id": self.iden,
            "parameters": self.params,
            "duration": self.duration,
            "send_response": self.send_response,
        }


class BlockIPActionContainer:
    """Deny access based on IP blacklist."""

    def __init__(self, action):
        self.ip_networks = Radix(None)
        self.insert(action)

    def insert(self, action):
        """Insert a new IP"""
        for blacklist in action.params["ip_cidr"]:
            self.ip_networks.insert(blacklist, '/' in blacklist, action)

    def remove(self, action):
        """Remove the IP from an action"""
        for blacklist in action.params["ip_cidr"]:
            self.ip_networks.remove(blacklist, '/' in blacklist)

    def actions(self):
        return self.ip_networks.all_payloads()


@register_action(ActionName.BLOCK_IP)
class BlockIPAction(BaseAction):
    """Action containing an IP block"""
    def __init__(self, *args, **kwargs):
        super(BlockIPAction, self).__init__(*args, **kwargs)
        self.name = ActionName.BLOCK_IP


@register_action(ActionName.REDIRECT_IP)
class RedirectIPAction(BaseAction):
    """Action containing a redirection on IP match"""
    def __init__(self, *args, **kwargs):
        super(RedirectIPAction, self).__init__(*args, **kwargs)
        self.target_url = self.params["url"]
        self.name = ActionName.REDIRECT_IP


@register_action(ActionName.BLOCK_USER)
class BlockUserAction(BaseAction):
    """Block an authenticated user."""

    def __init__(self, *args, **kwargs):
        super(BlockUserAction, self).__init__(*args, **kwargs)
        self.name = ActionName.BLOCK_USER
        self.users = self.params["users"]


@register_action(ActionName.REDIRECT_USER)
class RedirectUserAction(BaseAction):
    """Redirects an authenticated user."""

    def __init__(self, *args, **kwargs):
        super(RedirectUserAction, self).__init__(*args, **kwargs)
        self.name = ActionName.REDIRECT_USER
        self.users = self.params["users"]
        self.target_url = self.params["url"]


class UnsupportedAction(Exception):
    """Exception raised when an action is not supported."""

    def __init__(self, action_name):
        self.action_name = action_name


def action_from_dict(data):
    """Load an action from a dict."""
    action_name = data["action"]
    if action_name not in _AVAILABLE_ACTIONS:
        raise UnsupportedAction(action_name)
    action_cls = _AVAILABLE_ACTIONS[action_name]
    action = action_cls(
        iden=data.get("action_id"),
        params=data.get("parameters"),
        duration=data.get("duration"),
        send_response=data.get("send_response", True),
    )
    return action


class ActionStore:
    """A store to manage all actions."""

    def __init__(self):
        self._actions = defaultdict(list)

    def clear(self):
        """Remove all actions from the store."""
        self._actions.clear()

    def add(self, action):
        """Add an action to the store."""

        # If we're blocking an IP, we will only use a single action in order to share the Radix tree
        if action.name in {ActionName.BLOCK_IP, ActionName.REDIRECT_IP}:
            if self._actions[action.name]:
                self._actions[action.name][0].insert(action)
            else:
                self._actions[action.name].append(BlockIPActionContainer(action))
        else:
            self._actions[action.name].append(action)

    # used by the daemon
    def all_actions(self):
        for action_type, act_list in self._actions.items():
            if (action_type in {ActionName.BLOCK_IP, ActionName.REDIRECT_IP}
                    and len(act_list) == 1
                    and isinstance(act_list[0], BlockIPActionContainer)):
                for a in act_list[0].actions():
                    yield a
            else:
                # the actions are simply stored in a list o/wise
                for a in act_list:
                    yield a

    def _delete_expired(self, action_name, now):
        """Delete expired actions with name *action_name*."""
        self._actions[action_name] = [
            action
            for action in self._actions[action_name]
            if not action.timeout or action.timeout >= now
        ]

    def _get_for_ip(self, action_name, ip):
        """Return the action matching an IP address, or None."""
        action_list = self._actions[action_name]
        if not action_list:
            return None

        # Do we match something?
        match = action_list[0].ip_networks.match(ip)
        if match is not None:
            # Expired action?
            if match.timeout is None or match.timeout >= time():
                return match
            action_list[0].remove(match)
        return None

    def get_for_ip(self, ip):
        """Return the action matching an IP address, or None."""
        return self._get_for_ip(ActionName.BLOCK_IP, ip) or self._get_for_ip(ActionName.REDIRECT_IP, ip)

    def _get_for_user(self, action_name, user_dict):
        """Return the action matching the given user, or None."""
        self._delete_expired(action_name, time())
        for action in self._actions[action_name]:
            for action_user in action.users:
                if action_user == user_dict:
                    return action
        return None

    def get_for_user(self, user_dict):
        """Return the action matching the given user, or None."""
        return self._get_for_user(ActionName.BLOCK_USER, user_dict) \
            or self._get_for_user(ActionName.REDIRECT_USER, user_dict)

    def reload_from_dicts(self, data):
        """Reload actions from a list of dicts.

        Unsupported actions are skipped and logged but do not trigger an error.
        The list of their names is returned at the end.
        """
        unsupported = []
        new_store = self.__class__()
        for action_data in data:
            try:
                action = action_from_dict(action_data)
            except UnsupportedAction:
                unsupported.append(action_data["action"])
            else:
                LOGGER.debug("Adding action %r" % action_data)
                new_store.add(action)
        if unsupported:
            LOGGER.error("Skipped unsupported actions: %r", unsupported)
        # To avoid race conditions, we replace the action backing store
        # only when the new one is ready and let the GC collect the old one.
        self._actions = new_store._actions
        return unsupported
