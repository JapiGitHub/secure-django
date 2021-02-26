# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class KafkaTransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        request = args[0] if args else kwargs.get("request")
        name = request.__class__.__name__
        if name.startswith("ProduceRequest"):
            op = "producer"
        elif name.startswith("FetchRequest"):
            op = "consumer"
        else:
            return

        transport = {
            "type": "kafka",
            "host": instance.host,
            "host_port": instance.port,
        }
        self.record_transport(op, transport)


class KafkaTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            KafkaTransportCallback.from_rule_dict({
                "name": "ecosystem_kafka",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "kafka.conn::BrokerConnection",
                    "method": "_send",
                },
                "callbacks": {},
            }, runner, storage)
        ]
