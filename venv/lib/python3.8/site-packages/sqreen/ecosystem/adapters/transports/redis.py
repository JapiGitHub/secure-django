# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin


class RedisTransportCallback(RecordTransportMixin, RuleCallback):

    def pre(self, instance, args, kwargs, options):
        try:
            host = kwargs["host"]
            port = kwargs["port"]
        except Exception:
            host, port = None, None

        transport = {
            "type": "redis",
            "host": host,
            "host_port": port,
        }
        self.record_transport("client", transport)


class RedisTransportAdapter:

    def instrumentation_callbacks(self, runner, storage):
        return [
            RedisTransportCallback.from_rule_dict({
                "name": "ecosystem_redis",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "redis.connection::Connection",
                    "method": "__init__",
                },
                "callbacks": {},
            }, runner, storage)
        ]
