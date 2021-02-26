# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#


class ClientTracer:

    def format_payload(self, scope, transport):
        if scope == "client":
            return {
                "transport": transport.get("type"),
                "host": transport.get("host"),
                "ip": transport.get("host_ip"),
                "port": transport.get("host_port"),
                "tracing_identifier": transport.get("tracing_identifier"),
            }
