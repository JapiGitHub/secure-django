# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class MySQLDbTransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        try:
            host = kwargs.get("host")
            if host is None:
                if args:
                    host = args[0]
                else:
                    host = "127.0.0.1"
            port = int(kwargs.get("port", 3306))
        except Exception:
            host, port = None, None

        transport = {
            "type": "mysql",
            "host": host,
            "host_port": port,
        }
        self.record_transport("client", transport)


class MySQLDbTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            MySQLDbTransportCallback.from_rule_dict({
                "name": "ecosystem_mysqldb",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "MySQLdb",
                    "method": "connect",
                    "strategy": "DBApi2",
                },
                "callbacks": {},
            }, runner, storage)
        ]
