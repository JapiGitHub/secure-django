# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Batch delivery method
"""
from logging import getLogger
from random import randint
from time import time

from .._vendors.sqreen_security_signal_sdk import Signal
from ..events import Attack, RequestRecord
from ..remote_exception import RemoteException
from ..utils import HAS_TYPING
from .simple import SimpleDeliverer

if HAS_TYPING:
    from typing import MutableMapping, MutableSequence, Sequence, Union

    from ..session import Session

LOGGER = getLogger(__name__)


class BatchDeliverer(SimpleDeliverer):
    """ Class responsible for batching events before sending them to backend
    """

    def __init__(
        self, session, batch_size, max_staleness, randomize_staleness=True
    ):
        # type: (Session, int, int, bool) -> None
        super(BatchDeliverer, self).__init__(session)
        self.batch_size = batch_size
        self.original_max_staleness = max_staleness
        self.max_staleness = max_staleness
        self.randomize_staleness = randomize_staleness

        self.current_batch = []  # type: MutableSequence[Union[RemoteException, Attack, RequestRecord, Signal]]
        self.first_seen = {}  # type: MutableMapping[str, float]

    def post_event(self, event):
        # type: (Union[RemoteException, Attack, RequestRecord, Signal]) -> None
        """ Post a single event
        """
        self.current_batch.append(event)
        if self.post_batch_needed(event):
            self.deliver_batch()

    def post_batch_needed(self, event):
        # type: (Union[RemoteException, Attack, RequestRecord, Signal]) -> bool
        """ Check if the batch should be posted
        """
        event_keys = self._event_keys(event)
        first_seen = False
        for event_key in event_keys:
            # No early return here: we need to update self.first_seen for all
            # events.
            if self._first_seen(event_key):
                first_seen = True
        return first_seen or self._max_batch_size() or self._stale()

    def _first_seen(self, event_key):
        # type: (str) -> bool
        """ Check if it's the first time we see an event type, if it's the case
        the batch should be delivered.
        Update the first_seen time
        """
        time_seen = self.first_seen.get(event_key)

        if time_seen is None:
            self.first_seen[event_key] = time()

        return time_seen is None

    def deliver_batch(self, resilently=True):
        # type: (bool) -> None
        """ Send the current batch to the backend.
        Reset the first_seen values and randomize the max_staleness
        """
        LOGGER.debug("Deliver batch")
        self.session.post_batch(self.current_batch, send_resiliently=resilently)

        # Clean current state
        self.current_batch = []
        now = time()

        for key in self.first_seen:
            self.first_seen[key] = now

        self._randomize_staleness()

    def _randomize_staleness(self):
        """ Update max_stalenness with up-to 10% of original amount.
        Do nothing if randomize_staleness is False
        """
        if self.randomize_staleness:
            random_decay = randint(0, self.original_max_staleness / 10)
            self.max_staleness = self.original_max_staleness + random_decay

    def drain(self, resiliently):
        # type: (bool) -> None
        """ Drain current batch if not empty
        """
        if self._not_empty_batch():
            self.deliver_batch(resilently=resiliently)

    def tick(self):
        """ Periodic check to send batch when needed
        """
        should_send = self._not_empty_batch() and self._stale()
        if should_send:
            self.deliver_batch()
        return should_send

    @classmethod
    def _event_keys(cls, event):
        # type: (Union[RemoteException, Attack, RequestRecord, Signal]) -> Sequence[str]
        if not isinstance(event, RequestRecord):
            return [cls._event_key(event)]
        result = []
        observed_dict = event.payload.get("observed", {})
        for attack_dict in observed_dict.get("attacks", []):
            result.append("att-{}".format(attack_dict["rule_name"]))
        for exc_dict in observed_dict.get("sqreen_exceptions", []):
            result.append("rex-{}".format(exc_dict["klass"]))
        for sdk_entry in observed_dict.get("sdk", []):
            result.append("sdk-{}".format(sdk_entry[0]))
        for signal_entry in observed_dict.get("signals", []):
            result.append("signal-{}".format(signal_entry.get("signal_name")))
        return result

    @classmethod
    def _event_key(cls, event):
        # type: (Union[RemoteException, Attack, Signal]) -> str
        """ Unique key for first seen time per event_type
        """
        if isinstance(event, RemoteException):
            return "rex-{}".format(event.exception_class)
        elif isinstance(event, Attack):
            return "att-{}".format(event.rule_name)
        elif isinstance(event, dict):
            return "signal-{}".format(event.get("signal_name"))
        else:
            raise NotImplementedError(
                "Unknown event type {}".format(type(event))
            )

    ###
    # Various checkers used for checking if current batch should be sent
    # or not to the backend
    ###

    def _max_batch_size(self):
        # type: () -> bool
        """ Check if the batch has reached it max size, if it's the case, the
        batch should be delivered.
        """
        return len(self.current_batch) >= self.batch_size

    def _not_empty_batch(self):
        # type: () -> bool
        """ Check if the current batch is not empty.
        """
        return len(self.current_batch) > 0

    def _stale(self):
        # type: () -> bool
        """ Check if one event has been seen more than max_staleness in the past
        """
        if self.first_seen:
            min_seen = min(self.first_seen.values())
            return (min_seen + self.max_staleness) < time()
        return False
