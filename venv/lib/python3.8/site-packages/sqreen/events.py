# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Sqreen attack event helpers and placeholder
"""
import traceback
from logging import getLogger

from ._vendors.sqreen_security_signal_sdk import Signal, Trace
from .remote_exception import backtrace_to_stack_trace, traceback_formatter
from .runtime_infos import get_agent_type
from .sanitizer import get_sanitizer

LOGGER = getLogger(__name__)


def get_context_payload():
    """ Return attack payload dependent on the context, right now stacktrace.
    """
    return {
        "context": {
            "backtrace": list(traceback_formatter(traceback.extract_stack()))
        }
    }


class Attack(object):
    def __init__(self, payload, rule_name):
        self.payload = payload
        self.rule_name = rule_name

    def to_dict(self):
        result = {}
        rule_payload = self.payload.get("rule", {})
        request_payload = self.payload.get("request", {})
        local_payload = self.payload.get("local", {})
        if "name" in rule_payload:
            result["rule_name"] = rule_payload["name"]
        if "rulespack_id" in rule_payload:
            result["rulespack_id"] = rule_payload["rulespack_id"]
        if "test" in rule_payload:
            result["test"] = rule_payload["test"]
        if "infos" in self.payload:
            result["infos"] = self.payload["infos"]
        if "time" in local_payload:
            result["time"] = local_payload["time"]
        if "remote_ip" in request_payload:
            result["client_ip"] = request_payload["remote_ip"]
        if "request" in self.payload:
            result["request"] = self.payload["request"]
        if "params" in self.payload:
            result["params"] = self.payload["params"]
        if "context" in self.payload:
            result["context"] = self.payload["context"]
        if "headers" in self.payload:
            result["headers"] = self.payload["headers"]
        return result


class RequestRecord(object):
    """Request record objects."""

    VERSION = "20171208"

    def __init__(self, payload):
        self.payload = payload

    def to_dict(self):
        """Export the record as a dict object."""
        result = {"version": self.VERSION}
        sensitive_values = False

        if "request" in self.payload:
            request_dict = self.payload["request"]
            result["request"] = request_dict
            if "client_ip" in request_dict:
                result["client_ip"] = request_dict.pop("client_ip")
        else:
            result["request"] = {}
        if "params" in self.payload:
            result["request"]["parameters"] = self.payload["params"]
        if "headers" in self.payload:
            result["request"]["headers"] = self.payload["headers"]
        if "endpoint" in self.payload:
            result["request"]["endpoint"] = self.payload["endpoint"]

        sanitizer = get_sanitizer()
        sanitized_request, sensitive_values = sanitizer.sanitize(result["request"])
        result["request"] = sanitized_request

        if "response" in self.payload:
            result["response"] = self.payload["response"]

        if "observed" in self.payload:
            observed_dict = self.payload["observed"]
            result["observed"] = observed_dict
            rulespack = None
            attacks = observed_dict.get("attacks", [])
            for attack_dict in attacks:
                rulespack = attack_dict.pop("rulespack_id", None) or rulespack
            if attacks and sensitive_values:
                observed_dict["attacks"] = list(sanitizer.sanitize_attacks(attacks))
            exceptions = observed_dict.get("sqreen_exceptions", [])
            for exc_dict in exceptions:
                payload_dict = exc_dict.pop("exception", None)
                if payload_dict:
                    exc_dict["message"] = payload_dict["message"]
                    exc_dict["klass"] = payload_dict["klass"]
                rulespack = exc_dict.pop("rulespack_id", None) or rulespack
            if exceptions and sensitive_values:
                observed_dict["sqreen_exceptions"] = list(sanitizer.sanitize_exceptions(exceptions, sensitive_values))
            if rulespack:
                result["rulespack_id"] = rulespack
            if "observations" in observed_dict:
                result["observed"]["observations"] = [
                    {"category": cat, "key": key, "value": value, "time": time}
                    for (cat, time, key, value) in observed_dict[
                        "observations"
                    ]
                ]
            if "sdk" in observed_dict:
                global_user_identifiers = None
                for entry in observed_dict["sdk"]:
                    if entry[0] == "identify":
                        global_user_identifiers = entry[2]
                        LOGGER.debug("sdk identifiers: %r", global_user_identifiers)
                        break
                sdk_events = []
                for entry in observed_dict["sdk"]:
                    if global_user_identifiers is not None and entry[0] == "track":
                        entry[3].setdefault("user_identifiers", global_user_identifiers)
                    sdk_events.append({"name": entry[0], "time": entry[1], "args": entry[2:]})
                result["observed"]["sdk"] = sdk_events

        if "local" in self.payload:
            result["local"] = self.payload["local"]
        return result

    def to_trace(self):
        """ Request record trace.
        """
        event_payload = self.to_dict()

        context = dict(type="http")
        data = []
        trace = Trace(
            type="trace",
            context_schema="http/2020-01-01T00:00:00.000Z",
            context=context,
            actor={},
            data=data,
            source="sqreen:agent:{}".format(get_agent_type()),
        )

        rulespack_id = event_payload.get("rulespack_id", "0000000000000000000000000000000000000000")
        for entry in event_payload.get("observed", {}).get("sqreen_exceptions", []):
            signal = Signal(
                type="point",
                signal_name="sq.agent.exception",
                time=entry["time"],
                source="sqreen:rule:{}:{}".format(entry.get("rulespack_id", rulespack_id), entry["rule_name"]),
                payload_schema="sqreen_exception/2020-01-01T00:00:00.000Z",
                payload={
                    "klass": entry["klass"],
                    "message": entry["message"],
                    "infos": entry.get("infos", {}),
                    "test": entry.get("test", False),
                },
                location={
                    "stack_trace": list(backtrace_to_stack_trace(entry["backtrace"])),
                }
            )
            data.append(signal)

        for entry in event_payload.get("observed", {}).get("attacks", []):
            signal = Signal(
                type="point",
                signal_name="sq.agent.attack.{}".format(entry.get("attack_type", "unknown")),
                time=entry["time"],
                source="sqreen:rule:{}:{}".format(entry.get("rulespack_id") or rulespack_id, entry["rule_name"]),
                payload_schema="attack/2020-01-01T00:00:00.000Z",
                payload={
                    "test": entry.get("test", False),
                    "block": entry.get("block", False),
                    "infos": entry.get("infos", {}),
                },
                location={},
            )
            backtrace = entry.get("backtrace")
            if backtrace:
                signal["location"]["stack_trace"] = list(backtrace_to_stack_trace(backtrace))
            data.append(signal)

        global_user_identifiers = None
        traits = None
        # Look for the user identifiers
        for entry in event_payload.get("observed", {}).get("sdk", []):
            if entry["name"] == "identify":
                args = entry["args"]
                global_user_identifiers = args[0]
                if len(args) > 1:
                    traits = args[1]
                LOGGER.debug("sdk identifiers: %r", global_user_identifiers)
                break
        for entry in event_payload.get("observed", {}).get("sdk", []):
            args = entry["args"]
            name = entry["name"]
            if name not in ("track", "auth_track", "signup_track",):
                LOGGER.debug("ignoring sdk event: %r", entry)
                continue
            event_name = args[0]
            if not event_name.startswith("sq."):
                event_name = "sq.sdk.{}".format(event_name)
            options = args[1]
            payload = {"properties": options.get("properties")}
            user_identifiers = options.get("user_identifiers")
            if user_identifiers != global_user_identifiers:
                payload["user_identifiers"] = user_identifiers
            schema = "track_event" if name == "track" else name
            data.append(Signal(
                type="point",
                signal_name=event_name,
                source="sqreen:sdk:{}".format(name),
                time=options.get("timestamp", entry["time"]),
                payload_schema="{}/2020-01-01T00:00:00.000Z".format(schema),
                payload=payload,
            ))

        for entry in event_payload.get("observed", {}).get("signals", []):
            data.append(entry)

        request = event_payload["request"]
        user_agent = request.get("user_agent")
        if user_agent:
            trace["actor"]["user_agent"] = user_agent

        client_ip = event_payload.get("client_ip")
        if client_ip is not None:
            trace["actor"]["ip_addresses"] = [client_ip]

        if global_user_identifiers:
            trace["actor"]["identifiers"] = global_user_identifiers
        if traits:
            trace["actor"]["traits"] = traits

        context["request"] = dict(event_payload["request"])
        response = event_payload.get("response")
        if response is not None:
            context["response"] = dict(response)

        trace["time"] = event_payload.get("local", {}).get("time")

        return trace
