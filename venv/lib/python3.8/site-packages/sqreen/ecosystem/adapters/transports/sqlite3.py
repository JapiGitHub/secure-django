# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class SQLite3TransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        transport = {
            "type": "sqlite",
            "host": "127.0.0.1",
        }
        self.record_transport("client", transport)


class SQLite3TransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            SQLite3TransportCallback.from_rule_dict({
                "name": "ecosystem_sqlite3",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "sqlite3.dbapi2",
                    "method": "connect",
                    "strategy": "DBApi2"
                },
                "callbacks": {},
            }, runner, storage)
        ]
