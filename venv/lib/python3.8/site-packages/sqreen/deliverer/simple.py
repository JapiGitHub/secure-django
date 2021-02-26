# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Simple delivery method that directly call session on event
"""

from .._vendors.sqreen_security_signal_sdk.compat_model import Signal
from ..events import Attack, RequestRecord
from ..remote_exception import RemoteException
from ..utils import HAS_TYPING

if HAS_TYPING:
    from typing import Mapping, Optional, Sequence, Union

    from ..session import Session


class SimpleDeliverer(object):
    """ Class responsible for send events to backend depending
    on their types
    """

    batch_size = 0
    original_max_staleness = 0
    max_staleness = 0

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def post_event(self, event):
        # type: (Union[RemoteException, Attack, RequestRecord, Signal]) -> Optional[Mapping]
        """ Post a single event
        """
        if isinstance(event, RemoteException):
            return self.session.post_sqreen_exception(event)
        if isinstance(event, Attack):
            return self.session.post_attack(event)
        if isinstance(event, RequestRecord):
            return self.session.post_request_record(event)
        if isinstance(event, dict):
            return self.session.post_signal(event)
        else:
            err_msg = "Unknown event type {}".format(type(event))
            raise NotImplementedError(err_msg)

    def post_metrics(self, metrics):
        # type: (Sequence[Mapping]) -> Optional[Mapping]
        """ Post metrics
        """
        return self.session.post_metrics(metrics)

    def drain(self, resiliently):
        # type: (bool) -> None
        """ Since everything is posted at once nothing needs to be done here
        """
        pass

    def tick(self):
        """ Since everything is posted at once nothing needs to be done here
        """
        pass
