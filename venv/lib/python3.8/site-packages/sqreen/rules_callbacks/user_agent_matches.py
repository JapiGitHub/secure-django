# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Look for badly behaved clients
"""
import logging
import sys

from ..rules_actions import RecordAttackMixin
from .regexp_rule import RegexpRule

LOGGER = logging.getLogger(__name__)

ERROR_STRING = (
    "<html><head><title>Internal Server Error</title></head>"
    "<body><h1><p>Internal Server Error</p></h1></body></html>"
)


class UserAgentMatchesCB(RecordAttackMixin, RegexpRule):
    def pre(self, instance, args, kwargs, options):
        environ = args[-2]
        start_response = args[-1]

        user_agent = environ.get("HTTP_USER_AGENT")
        if not user_agent:
            return

        match = self.match_regexp(user_agent)
        if not match:
            return

        infos = {"found": match, "in": user_agent}
        self.record_attack(infos)

        # Try to detect gunicorn
        server_is_gunicorn = environ.get("SERVER_SOFTWARE", "").startswith(
            "gunicorn"
        )
        is_gevent_loaded = "gevent" in sys.modules
        if server_is_gunicorn and is_gevent_loaded and self.block:
            # Log the error
            err = "Sqreen blocked a security threat (type: #%s). No action is required."
            LOGGER.error(err, self.rule_name)

            # Return a 500 error instead for gunicorn
            start_response(
                "500 Internal Server Error",
                [
                    ("Content-Type", "text/html"),
                    ("Content-Length", str(len(ERROR_STRING))),
                ],
            )

            return {"status": "override", "new_return_value": [ERROR_STRING]}
        else:
            # Blocking is checked by the caller
            return {
                "status": "raise",
                "data": match,
                "rule_name": self.rule_name,
            }
