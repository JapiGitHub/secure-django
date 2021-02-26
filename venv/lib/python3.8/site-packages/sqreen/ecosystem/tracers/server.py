# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#


class ServerTracer:

    def format_payload(self, scope, transport):
        if scope == "server":
            return {
                "transport": "http",
                "client_ip": transport.get("client_ip"),
                "host": transport.get("hostname"),
                "port": transport.get("server_port"),
                "tracing_identifier": transport.get("tracing_identifier"),
            }
