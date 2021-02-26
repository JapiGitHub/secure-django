# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#


class ProducerTracer:

    def format_payload(self, scope, transport):
        if scope == "producer":
            return {
                "message_type": transport.get("type"),
                "topic": transport.get("topic"),
                "host": transport.get("host"),
                "ip": transport.get("host_ip"),
                "port": transport.get("host_port"),
                "tracing_identifier": transport.get("tracing_identifier"),
            }
