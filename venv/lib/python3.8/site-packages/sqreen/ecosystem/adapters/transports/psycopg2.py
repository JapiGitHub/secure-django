# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class Psycopg2TransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        try:
            # TODO parse args[0] if provided
            host = kwargs.get("host", "127.0.0.1")
            port = int(kwargs.get("port", 5432))
        except Exception:
            host, port = None, None

        transport = {
            "type": "postgres",
            "host": host,
            "host_port": port,
        }
        self.record_transport("client", transport)


class Psycopg2TransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            Psycopg2TransportCallback.from_rule_dict({
                "name": "ecosystem_psycopg2",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "psycopg2",
                    "method": "connect",
                    "strategy": "psycopg2",
                },
                "callbacks": {},
            }, runner, storage)
        ]
