# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class HttpClientTransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        try:
            host_ip, host_port = instance.sock.getpeername()
        except Exception:
            host_ip, host_port = None, None

        host = instance.host
        if ":" in host:
            try:
                host, host_port = host.split(":", 1)
                host_port = int(host_port)
            except Exception:
                pass

        transport = {
            "type": "http",
            "host": host or host_ip,
            "host_ip": host_ip,
            "host_port": host_port,
        }

        if not self.record_transport("client", transport):
            return

        tracing_identifier = transport.get("tracing_identifier")
        if tracing_identifier is None:
            return

        new_args = list(args)
        new_headers = new_args[3] = dict(args[3])
        new_headers["X-Sqreen-Trace-Identifier"] = tracing_identifier
        return {
            "status": "modify_args",
            "args": (new_args, kwargs),
        }


class HttpClientTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            HttpClientTransportCallback.from_rule_dict({
                "name": "ecosystem_http_client",
                "rulespack_id": "ecosystem/transport",
                "block": True,
                "test": False,
                "hookpoint": {
                    "klass": "http.client::HTTPConnection",
                    "method": "_send_request"
                },
                "callbacks": {},
            }, runner, storage)
        ]
