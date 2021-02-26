# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import sys

from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin

if sys.version_info[0] >= 3:
    import urllib.parse as urlparse
else:
    import urlparse


class BotocoreTransportCallback(RecordTransportMixin, RuleCallback):

    FILTERED_OPERATIONS = {
        "kinesis": {
            "PutRecord": "producer",
            "PutRecords": "producer",
            "GetRecords": "consumer",
        },
        "sqs": {
            "SendMessage": "producer",
            "SendMessageBatch": "producer",
            "ReceiveMessage": "consumer",
        },
    }

    def pre(self, instance, args, kwargs, options):
        operation_model = args[0] if args else kwargs.get("operation_model")
        service_name = operation_model.service_model.service_name.lower()
        operations = self.FILTERED_OPERATIONS.get(service_name)
        if operations is None:
            return
        op = operations.get(operation_model.name)
        if op is None:
            return

        try:
            host = urlparse.urlparse(instance.host).netloc
            if ":" in host:
                host, port = host.split(":", 1)
                port = int(port)
            else:
                port = None
        except Exception:
            host, port = None, None

        transport = {
            "type": "aws-{}".format(service_name),
            "host": host,
            "host_port": port,
        }
        self.record_transport(op, transport)


class BotocoreTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            BotocoreTransportCallback.from_rule_dict({
                "name": "ecosystem_botocore",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "botocore.endpoint::Endpoint",
                    "method": "make_request",
                },
                "callbacks": {},
            }, runner, storage)
        ]
