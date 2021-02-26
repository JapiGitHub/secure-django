# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Reactive Engine
"""
import logging
from bisect import bisect
from copy import copy
from itertools import chain
from operator import attrgetter
from weakref import WeakSet

from .execute_callbacks import execute_callbacks
from .utils import viewkeys

LOGGER = logging.getLogger(__name__)


class SpanDisposed(Exception):
    """
    Exception raised when a span is used after it was disposed.
    """


class SpanSettings(object):

    def __init__(self, callbacks=None):
        self._callbacks_by_addr = callbacks or {}

    def callbacks_for_addresses(self, addresses):
        """
        Return a callbacks interested by addresses. The callbacks
        are sorted by order of priority.
        """
        # Sort callbacks by priority
        it = sorted(chain.from_iterable([self._callbacks_by_addr.get(addr, ()) for addr in addresses]),
                    key=attrgetter("priority"))
        prev = None
        for callback in it:
            # Deduplicate callbacks
            if callback is prev:
                continue
            yield callback
            prev = callback

    def _add_callback(self, callback, addresses):
        for addr in addresses:
            callbacks = self._callbacks_by_addr.setdefault(addr, [])
            idx = bisect([c.priority for c in callbacks], callback.priority)
            callbacks.insert(idx, callback)

    def add_callback(self, callback):
        """
        Register a callback to the reactive engine span.
        """
        addresses = callback.batch_addresses
        authorized_addresses = callback.authorized_addresses
        if addresses:
            not_authorized = addresses.difference(authorized_addresses)
            if not_authorized:
                raise ValueError("Callback {!r} is not authorized to register {!r}"
                                 .format(callback, not_authorized))
        for addresses in callback.group_addresses:
            not_authorized = addresses.difference(authorized_addresses)
            if not_authorized:
                raise ValueError("Callback {!r} is not authorized to register {!r}"
                                 .format(callback, not_authorized))
        if addresses:
            LOGGER.debug("Callback %r subscribes to any of %r", callback, addresses)
            self._add_callback(callback, addresses)
        for addresses in callback.group_addresses:
            LOGGER.debug("Callback %r subscribes to group %r", callback, addresses)
            self._add_callback(callback, addresses)

    def remove_callbacks(self):
        """
        Remove all callbacks from the reactive engine.

        Note: callbacks can still get called on children span until they are disposed.
        """
        self._callbacks_by_addr = {}

    @property
    def subscribed_addresses(self):
        """
        List all subscribed addresses.
        """
        return viewkeys(self._callbacks_by_addr)

    def __copy__(self):
        return self.__class__(dict(self._callbacks_by_addr))

    def __enter__(self):
        self._tmp = copy(self)
        return self._tmp

    def __exit__(self, exc_type, exc_value, traceback):
        tmp = self.__dict__.pop("_tmp", None)
        if tmp is None or exc_type is not None:
            return
        # Atomic switch to new callbacks
        self._callbacks_by_addr = tmp._callbacks_by_addr


class Span:

    _none = object()

    def __init__(self, settings=None):
        self.settings = settings or SpanSettings()
        self._children = WeakSet()
        self._state = {}

    def create_child(self):
        settings = self.settings
        if settings is None:
            raise SpanDisposed
        span = self.__class__(copy(settings))
        span._state.update(self._state)
        self._children.add(span)
        return span

    def dispose(self):
        """
        Dispose a span and all its children. This method is not thread-safe.
        """
        self._state.clear()
        self.settings = None
        while len(self._children):
            self._children.pop(0).dispose()

    @property
    def subscribed_addresses(self):
        """
        List all subscribed addresses.
        """
        settings = self.settings
        if settings:
            return settings.subscribed_addresses

    def _callbacks_for_data(self, data):
        """
        Mutate data to add grouped addresses and return callbacks interested
        by the data.
        """
        settings = self.settings
        if settings is None:
            raise SpanDisposed
        for callback in settings.callbacks_for_addresses(viewkeys(data)):
            group_addresses = callback.group_addresses
            if group_addresses:
                groups_data = []
                for group in group_addresses:
                    group_data = []
                    for addr in group:
                        value = data.get(addr, self._none)
                        if value is not self._none:
                            self._state[addr] = value
                        else:
                            value = self._state.get(addr, self._none)
                        if value is not self._none:
                            group_data.append((addr, value))
                    if len(group_data) == len(group):
                        groups_data.extend(group_data)
                if groups_data:
                    data.update(groups_data)
                    yield callback
                elif callback.batch_addresses:
                    yield callback
            elif callback.batch_addresses:
                yield callback

    def provide_data(self, data, **options):
        callbacks_data = dict(data)
        callbacks = list(self._callbacks_for_data(callbacks_data))
        if callbacks:
            options["span"] = self
            return execute_callbacks(
                callbacks, "handler", None,
                (callbacks_data,), {}, options,
                valid_actions=["raise"]
            )

    def __del__(self):
        self.dispose()


class Engine:
    """
    Reactive Engine dispatches available data to callbacks.

    Data is a mapping between addresses and values. Data is made available on
    a span, describing its lifetime.

    Spans are layed out in a structured tree. A child span cannot outlive its
    parent (once it is disposed all children spans are disposed too).
    """

    def __init__(self):
        self.root = Span()

    @property
    def settings(self):
        return self.root.settings

    def create_span(self, parent=None):
        """
        Create a new span inheriting the given parent state.

        The spans are automatically disposed when there are no more references.
        """
        parent = parent or self.root
        return parent.create_child()

    def provide_data(self, data, span=None, **kwargs):
        """
        Provide data on the given span.

        Note: changes are not propagated to descendant spans.
        """
        span = span or self.root
        return span.provide_data(data, **kwargs)

    @property
    def subscribed_addresses(self):
        """
        List all subscribed addresses.
        """
        return self.root.subscribed_addresses
