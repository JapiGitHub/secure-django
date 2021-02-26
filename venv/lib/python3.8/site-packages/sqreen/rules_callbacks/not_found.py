# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Look for 404 error
"""
import logging
import os

from ..exceptions import InvalidArgument
from ..rules import RuleCallback
from ..rules_actions import RecordAttackMixin
from ..utils import Mapping

LOGGER = logging.getLogger(__name__)


class NotFoundCB(RecordAttackMixin, RuleCallback):
    """Record attack for suspicious not found errors."""

    def __init__(self, *args, **kwargs):
        super(NotFoundCB, self).__init__(*args, **kwargs)

        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        try:
            self.ignore_extensions = {'.{}'.format(e) for e in self.data['values'][0]["extensions"]}
        except KeyError as missing:
            msg = "mising key in data (had {}) {!r}"
            raise InvalidArgument(msg.format(self.data.keys(), missing))

        self.max_extensions_size = max([len(e) for e in self.ignore_extensions])

    def post(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        response = self.storage.get_current_response()
        if response is not None and response is not None \
                and response.status_code == 404:
            path = request.path
            _, maybe_ext = os.path.splitext(path)
            if len(maybe_ext) > self.max_extensions_size \
                    or maybe_ext.lower() not in self.ignore_extensions:
                infos = {
                    "path": path,
                    "host": request.hostname,
                    "verb": request.method,
                    "ua": request.client_user_agent,
                }
                self.record_attack(infos)
