# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Contains all callback classes
"""
import logging

from ..exceptions import InvalidSignature
from ..remote_exception import RemoteException
from ..rules import BaseCallback
from ..runtime_storage import runtime
from ..utils import HAS_ASYNCIO
from .auth_metrics import (
    AuthMetricsCB,
    DjangoAuthMetrics,
    SDKAuthMetrics,
    SDKSignupMetrics,
)
from .binding_accessor_counter import BindingAccessorCounter
from .binding_accessor_matcher import BindingAccessorMatcherCallback
from .binding_accessor_provide_data import BindingAccessorProvideData
from .binding_accessor_return_value import BindingAccessorReturnValue
from .count_http_codes import CountHTTPCodesCB
from .count_http_codes_django import CountHTTPCodesCBDjango
from .count_http_codes_flask import CountHTTPCodesCBFlask
from .count_http_codes_php import CountHTTPCodesCBPHP
from .count_http_codes_pyramid import CountHTTPCodesCBPyramid
from .crawler_user_agent_matches_metrics import (
    CrawlerUserAgentMatchesMetricsCB,
)
from .extension_passthru import ExtensionPassthruCB
from .headers_insert import HeadersInsertCB
from .headers_insert_django import HeadersInsertCBDjango
from .headers_insert_flask import HeadersInsertCBFlask
from .headers_insert_pyramid import HeadersInsertCBPyramid
from .headers_transform import HeadersTransform
from .ip_blacklist import IPBlacklistCB
from .not_found import NotFoundCB
from .reactive_log import ReactiveLog
from .reactive_waf import ReactiveWAF
from .record_request import RecordRequest
from .record_request_context import RecordRequestContext
from .record_request_context_django import RecordRequestContextDjango
from .record_request_context_flask import RecordRequestContextFlask
from .record_request_context_pyramid import RecordRequestContextPyramid
from .record_request_django import RecordRequestDjango
from .record_request_flask import RecordRequestFlask
from .record_request_pyramid import RecordRequestPyramid
from .record_response import RecordResponse
from .reflected_xss import ReflectedXSSCB
from .regexp_rule import RegexpRule
from .security_responses import (
    IPActionCB,
    SecurityResponsesIP,
    SecurityResponsesUser,
)
from .shell_env import ShellEnvCB
from .sqreen_error_page import SqreenErrorPage
from .sqreen_error_page_django import SqreenErrorPageDjango
from .sqreen_error_page_django_new_style import SqreenErrorPageDjangoNewStyle
from .sqreen_error_page_flask import SqreenErrorPageFlask
from .sqreen_error_page_pyramid import SqreenErrorPagePyramid
from .user_agent_matches import UserAgentMatchesCB
from .user_agent_matches_framework import (
    UserAgentMatchesCBDjango,
    UserAgentMatchesCBFramework,
)
from .user_monitoring import (
    DjangoAuthTrack,
    SDKAuthTrack,
    SDKIdentify,
    SDKSignupTrack,
    SDKTrackEvent,
)
from .waf import WAFCB
from .wsgi_input_preview import WSGIInputPreview

# Workaround for Jenkins build.
try:
    from .js import JSCB
except ImportError:
    pass

if HAS_ASYNCIO:
    from .count_http_codes_aiohttp import CountHTTPCodesCBAioHTTP
    from .headers_insert_aiohttp import HeadersInsertCBAioHTTP
    from .record_request_context_aiohttp import RecordRequestContextAioHTTP
    from .sqreen_error_page_aiohttp import SqreenErrorPageAioHTTP


LOGGER = logging.getLogger(__name__)


def cb_from_rule(rule, runner, rule_verifier=None, storage=runtime):
    """ Instantiate the right cb class
    """
    # Fixme clean

    if not isinstance(rule, dict):
        LOGGER.debug("Invalid rule type %s", type(rule))
        return

    # Check rule signature
    if rule_verifier is not None \
            and not rule_verifier.verify_rule(rule):
        LOGGER.critical("Can't verify signature of rule %s", rule["name"])
        raise InvalidSignature(rule["name"], rule["rulespack_id"])

    hookpoint = rule.get("hookpoint", {})
    # Ask for native attack rendering
    if "attack_render_info" in hookpoint:
        callback_class_name = "ExtensionPassthruCB"
    # Use JSCB for internal_js_hook callback used in PHP
    elif hookpoint.get("strategy") == "internal_js_hook":
        callback_class_name = "JSCB"
    else:
        callback_class_name = hookpoint.get("callback_class")

    # Default to JS callbacks for hookpoint
    if callback_class_name is None:
        callback_class_name = "JSCB"

    possible_subclass = globals().get(callback_class_name, None)

    if possible_subclass and issubclass(possible_subclass, BaseCallback):
        try:
            return possible_subclass.from_rule_dict(rule, runner, storage=storage)
        except Exception:
            LOGGER.warning(
                "Couldn't instantiate a callback for rule %s",
                rule,
                exc_info=True,
            )
            infos = {
                "rule_name": rule["name"],
                "rulespack_id": rule["rulespack_id"],
            }
            remote_exception = RemoteException.from_exc_info(callback_payload=infos)
            runner.queue.put(remote_exception)
            return

    LOGGER.debug(
        "Couldn't find the class matching class_name %s", callback_class_name
    )
    return


__all__ = [
    "AuthMetricsCB",
    "BindingAccessorCounter",
    "BindingAccessorMatcherCallback",
    "BindingAccessorProvideData",
    "BindingAccessorReturnValue",
    "cb_from_rule",
    "CountHTTPCodesCB",
    "CountHTTPCodesCBAioHTTP",
    "CountHTTPCodesCBDjango",
    "CountHTTPCodesCBFlask",
    "CountHTTPCodesCBPHP",
    "CountHTTPCodesCBPyramid",
    "CrawlerUserAgentMatchesMetricsCB",
    "DjangoAuthTrack",
    "DjangoAuthMetrics",
    "ExtensionPassthruCB",
    "HeadersInsertCB",
    "HeadersInsertCBAioHTTP",
    "HeadersInsertCBDjango",
    "HeadersInsertCBFlask",
    "HeadersInsertCBPyramid",
    "HeadersTransform",
    "IPActionCB",
    "IPBlacklistCB",
    "JSCB",
    "NotFoundCB",
    "NotFoundCBDjango",
    "NotFoundCBFlask",
    "ReactiveLog",
    "ReactiveWAF",
    "RecordRequest",
    "RecordRequestDjango",
    "RecordRequestFlask",
    "RecordRequestPyramid",
    "RecordRequestContext",
    "RecordRequestContextAioHTTP",
    "RecordRequestContextDjango",
    "RecordRequestContextFlask",
    "RecordRequestContextPyramid",
    "RecordResponse",
    "ReflectedXSSCB",
    "RegexpRule",
    "SDKAuthTrack",
    "SDKAuthMetrics",
    "SDKIdentify",
    "SDKSignupTrack",
    "SDKSignupMetrics",
    "SDKTrackEvent",
    "SecurityResponsesIP",
    "SecurityResponsesUser",
    "ShellEnvCB",
    "SqreenErrorPage",
    "SqreenErrorPageAioHTTP",
    "SqreenErrorPageDjango",
    "SqreenErrorPageDjangoNewStyle",
    "SqreenErrorPageFlask",
    "SqreenErrorPagePyramid",
    "UserAgentMatchesCB",
    "UserAgentMatchesCBDjango",
    "UserAgentMatchesCBFramework",
    "WAFCB",
    "WSGIInputPreview",
]
