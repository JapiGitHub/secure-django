# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Sqreen exceptions
"""

import logging
import traceback

LOGGER = logging.getLogger(__name__)


class SqreenException(Exception):
    """ Base exception for all sqreen exceptions
    """

    def __str__(self):
        return self.__repr__()

    def exception_infos(self):
        return {}


class InvalidApplicationName(SqreenException):
    """ Exception raised when the application name is invalid.
    """
    pass


class InvalidSignature(SqreenException):
    """ Exception raised when encountering an invalid rule signature
    """

    def __init__(self, name, rulespack_id):
        self.callback_payload = {
            "rule_name": name,
            "rulespack_id": rulespack_id,
        }


class InvalidArgument(SqreenException):
    """ Exception raised when sqreen code receive invalid arguments like bad
    rule dict.
    """
    pass


class RequestStoreFull(SqreenException):
    """ Exception raised when the request store is full.
    """
    pass


class RequestBlocked(SqreenException):
    """Base class for blocking requests (because of attack or action)."""

    def __init__(self):
        self._pending = True

    def done(self):
        """Mark the blocking as done.

        If the exception is not marked as done, an error is triggered when
        the object is destroyed.
        """
        self._pending = False

    def __del__(self):
        if not self._pending:
            return  # All right.
        LOGGER.error(
            "Exception %r was destroyed but it is pending!",
            self.__class__.__name__,
        )
        LOGGER.debug("\n".join(traceback.format_stack()))


# This exception name is particularly important since it is often seen by
# Sqreen users when watching their logs. It should not raise any concern to
# them.
class AttackBlocked(RequestBlocked):
    """ Raised when a callback detected an attack
    """

    def __init__(self, rule_name):
        super(AttackBlocked, self).__init__()
        self.rule_name = rule_name

    def __repr__(self):
        msg = "Sqreen blocked a security threat (type: #{}). No action is required."
        return msg.format(self.rule_name)


class BaseAction(RequestBlocked):
    """Base class when a callback triggers a security action."""

    def __init__(self, action_id):
        super(BaseAction, self).__init__()
        self.action_id = action_id


class ActionBlock(BaseAction):
    """Exception raised when a security action blocks a request."""

    def __repr__(self):
        return (
            "Sqreen blocked a request (action_id: {}). "
            "No action is required.".format(self.action_id)
        )


class ActionRedirect(BaseAction):
    """Exception raised when a security action redirects a request."""

    def __init__(self, action_id, target_url):
        super(ActionRedirect, self).__init__(action_id)
        self.target_url = target_url

    def __repr__(self):
        return (
            "Sqreen redirected a request to {!r} (action_id: {}). "
            "No action is required".format(self.target_url, self.action_id)
        )


class MissingDataException(Exception):
    """ Exception that occurs when trying to access undefined binding accessor """

    def __init__(self, binding_accessor):
        self.binding_accessor = binding_accessor


###
# HTTP Exceptions
###


class SqreenHttpException(SqreenException):
    pass


class InvalidJsonResponse(SqreenHttpException):
    def __init__(self, parsing_exception):
        self.parsing_exception = parsing_exception

    def __repr__(self):
        msg = "An error occurred while trying to parse the response: {!r}"
        return msg.format(self.parsing_exception)


class StatusFailedResponse(SqreenHttpException):
    def __init__(self, response):
        self.response = response

    def __repr__(self):
        msg = "Response returned with a status false: {!r}"
        return msg.format(self.response)


class InvalidStatusCodeResponse(SqreenHttpException):
    def __init__(self, status, response_data=None):
        self.status = status
        self.response_data = response_data

    def __repr__(self):
        msg = "Response status code is invalid: {!r}"
        return msg.format(self.status)


# Incompotible exceptions that may be raised at startup


class UnsupportedFrameworkVersion(Exception):
    def __init__(self, framework, version):
        self.framework = framework
        self.version = version

    def __str__(self):
        return "{} in version {} is not supported".format(
            self.framework.title(), self.version
        )


class UnsupportedPythonVersion(Exception):
    def __init__(self, python_version):
        self.python_version = python_version

    def __str__(self):
        return "Python version {} is unsupported".format(self.python_version)
