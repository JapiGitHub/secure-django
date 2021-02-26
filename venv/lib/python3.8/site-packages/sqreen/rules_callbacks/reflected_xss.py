# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Reflected XSS callback
"""
import sys
from logging import getLogger

from ..rules_actions import RecordAttackMixin
from ..utils import STRING_CLASS, UNICODE_CLASS, is_string
from .regexp_rule import RegexpRule

if sys.version_info >= (3, 2):
    # Added in Python 3.2
    from html import escape
else:
    # Removed in Python 3.8
    from cgi import escape


LOGGER = getLogger(__name__)


class ReflectedXSSCB(RecordAttackMixin, RegexpRule):
    def post(self, instance, args, kwargs, options):
        """ Check if a template node returns a content that is in the
        query parameters
        """
        request = self.storage.get_current_request()
        result = options.get("result")

        if not request:
            LOGGER.warning("No request was recorded abort")
            return

        if not is_string(result):
            LOGGER.debug("Non string passed, type %s", type(result))
            return

        if request.params_contains(result):
            # If the payload is malicious, record the attack
            matching_regexp = self.match_regexp(result)
            if matching_regexp:
                self.record_attack(
                    {"found": matching_regexp, "payload": result}
                )

            # Only if the callback should block, sanitize the string
            if self.block:
                return {
                    "status": "override",
                    "new_return_value": self._escape(result),
                }

    @staticmethod
    def _escape(value):
        """ Escape a malicious value to make it safe
        """

        # Convert the value if it's a string subclass to bypass escape
        value_class = value.__class__
        if value_class not in (STRING_CLASS, UNICODE_CLASS):
            bases = value_class.__bases__

            if UNICODE_CLASS in bases:
                value = UNICODE_CLASS(value)
            elif STRING_CLASS in bases:
                value = STRING_CLASS(value)
            else:
                err_msg = "Value '{!r}' has invalid type and bases: {!r}"
                raise TypeError(err_msg.format(value, bases))

        # Convert to str before avoiding problems with Jinja2 Markup classes
        return escape(value, True)
