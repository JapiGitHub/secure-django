# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class PyMongoTransportCallback(RecordTransportMixin, RuleCallback):

    def post(self, instance, args, kwargs, options):
        topology_settings = args[0]
        for host, port in topology_settings.seeds:
            transport = {
                "type": "mongo",
                "host": host,
                "host_port": port,
            }
            self.record_transport("client", transport)


class PyMongoTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            PyMongoTransportCallback.from_rule_dict({
                "name": "ecosystem_pymongo",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "pymongo.topology::Topology",
                    "method": "__init__"
                },
                "callbacks": {},
            }, runner, storage)
        ]
