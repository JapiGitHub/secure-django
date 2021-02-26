# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Framework Transport Adapter
"""

from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class FrameworkTransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        request = self.storage.get_current_request()
        if request is None:
            return
        transport = {
            "type": "http",
            "client_ip": request.client_ip,
            "hostname": request.hostname,
            "server_port": request.server_port,
            "tracing_identifier": request.request_headers["HTTP_X_SQREEN_TRACE_IDENTIFIER"],
        }
        self.record_transport("server", transport)
