# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Remote exception module
"""
import sys
import traceback

from .utils import now


def traceback_formatter(backtrace):
    """ Accept a backtrace in the format of traceback.extract_tb or
    traceback.extract_stack and returns a list of dictionary matching this
    format::

    {
        'file': FILENAME,
        'line_number': LINE_NUMBER,
        'method': FUNCTION_NAME
    }
    """
    frames = []
    for frame in backtrace:
        filename, line_number, function_name, _ = frame
        frames.append(
            {
                "file": filename,
                "line_number": line_number,
                "method": function_name,
            }
        )
    return frames


def raw_traceback_formatter(raw_backtrace):
    """ Accept a traceback object, convert it to a traceback and returns the
    same format than backtrack_formatter.
    """
    return traceback_formatter(traceback.extract_tb(raw_backtrace))


def backtrace_to_stack_trace(backtrace):
    """Adapt backtraces to the signal stack trace format.
    """
    for frame in backtrace:
        abs_path = frame.get("file")
        yield {
            "function": frame.get("method", frame.get("function")),
            "abs_path": abs_path,
            "lineno": frame.get("line_number", frame.get("line")),
            "in_app": "sqreen" not in abs_path if abs_path else False,
        }


class RemoteException(object):
    def __init__(
        self,
        name,
        msg,
        raw_backtrace=None,
        callback_payload=None,
        exception_payload=None,
        request_payload=None,
        stack=None,
        at=None,
    ):
        self.exception_class = name
        self.exception_msg = msg

        if at is None:
            at = now()
        self.at = at

        self.raw_backtrace = raw_backtrace
        if raw_backtrace is not None:
            self.backtrace = raw_traceback_formatter(self.raw_backtrace)
        else:
            self.backtrace = []

        self.stack = None
        if stack is not None:
            self.stack = traceback_formatter(stack)
            self.backtrace = self.stack + self.backtrace

        if callback_payload is None:
            callback_payload = {}
        self.callback_payload = callback_payload

        self.exception_payload = exception_payload
        self.request_payload = request_payload

    @classmethod
    def from_exc_info(cls, exc_info=None, **kwargs):
        """ Create a RemoteException from sys.exc_info.
        """
        if exc_info is None:
            exc_info = sys.exc_info()
        return cls(exc_info[0].__name__, str(exc_info[1]), raw_backtrace=exc_info[2], **kwargs)

    def to_dict(self):
        """ Returns information about exception, backtrace and request merged
        into initial payload
        """
        base_payload = {"infos": {}}

        # Base fields
        base_payload["rule_name"] = self.callback_payload.pop(
            "rule_name", None
        )
        base_payload["rulespack_id"] = self.callback_payload.pop(
            "rulespack_id", None
        )
        base_payload["rule_signature"] = self.callback_payload.pop(
            "rule_signature", None
        )

        if self.callback_payload:
            base_payload["infos"]["callback"] = self.callback_payload

        if self.exception_payload:
            base_payload["infos"]["exception"] = self.exception_payload

        if self.request_payload:
            base_payload.update(self.request_payload)

        base_payload.update(
            {
                "klass": self.exception_class,
                "message": self.exception_msg,
                "context": {"backtrace": self.backtrace},
            }
        )

        return base_payload

    def to_signal(self):
        """ Exception signal.
        """
        signal = dict(
            type="point",
            signal_name="sq.agent.exception",
            payload_schema="sqreen_exception/2020-01-01T00:00:00.000Z",
        )

        rule_name = self.callback_payload.pop("rule_name", None)
        if rule_name is not None:
            rulespack_id = self.callback_payload.pop(
                "rulespack_id", "0000000000000000000000000000000000000000")
            signal["source"] = "sqreen:rule:{}:{}".format(rulespack_id, rule_name)
        else:
            signal["source"] = "sqreen:agent:python"

        signal["time"] = self.at
        signal["location"] = {
            "stack_trace": list(backtrace_to_stack_trace(self.backtrace))
        }

        infos = {}
        if self.callback_payload:
            infos["callback"] = dict(self.callback_payload)

        if self.exception_payload:
            infos["exception"] = self.exception_payload

        signal["payload"] = {
            "klass": self.exception_class,
            "message": self.exception_msg,
            "infos": infos,
        }

        if self.request_payload:
            signal["payload"].update(self.request_payload)

        return signal
