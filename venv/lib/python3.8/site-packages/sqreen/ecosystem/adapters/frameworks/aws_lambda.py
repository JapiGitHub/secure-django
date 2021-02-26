# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" AWS Lambda Adapter
"""
import base64
import logging
import sys

from ....frameworks.base import BaseRequest, BaseResponse
from ....rules import RuleCallback
from ....rules_actions import RecordTransportMixin
from ....rules_callbacks import (
    BindingAccessorCounter,
    BindingAccessorProvideData,
    CountHTTPCodesCB,
    RecordRequestContext,
)
from ....rules_callbacks.sqreen_error_page import BaseSqreenErrorPage
from ....utils import Iterable, Mapping, is_string
from ..transports.framework import FrameworkTransportCallback

LOGGER = logging.getLogger(__name__)


class AWSLambdaEvent(dict):

    def has(self, *args):
        NONE = object()
        obj = self
        for arg in args:
            obj = obj.get(arg, NONE)
            if obj is NONE:
                return False
        return True

    @property
    def guess_service(self):
        """
        This property will guess the event originating AWS service.
        """
        if self.has("requestContext", "elb"):
            return "elastic-load-balancer"
        elif self.has("requestContext", "resourcePath"):
            return "api-gateway-rest"
        elif self.has("requestContext", "http"):
            return "api-gateway-http"
        elif "detail-type" in self:
            return "cloudwatch"
        elif "awslogs" in self:
            return "cloudwatch-log"
        elif "identityPoolId" in self or "userPoolId" in self:
            return "cognito"
        elif "StackId" in self:
            return "cloudformation"
        elif "CodePipeline.job" in self:
            return "codepipeline"
        elif self.get("eventSource") == "aws:kafka":
            return "kafka"
        elif "sourceKinesisStreamArn" in self:
            return "firehose"
        elif "currentIntent" in self:
            return "lex"
        elif "configRuleId" in self:
            return "config"
        elif "batteryVoltage" in self:
            return "button"
        elif self.has("payload", "switchControlAction"):
            return "alexa"
        elif self.has("context", "AudioPlayer"):
            return "alexa-skill"
        records = self.get("Records", [])
        if not records:
            return "unknown"
        first_record = records[0]
        if "cf" in first_record:
            return "cloudfront"
        elif "s3" in first_record:
            return "s3"
        elif "codecommit" in first_record:
            return "codecommit"
        elif "dynamodb" in first_record:
            return "dynamodb"
        elif "kinesis" in first_record:
            return "kinesis"
        elif "ses" in first_record:
            return "ses"
        elif "Sns" in first_record:
            return "sns"
        elif first_record.get("eventSource") == "aws:sqs":
            return "sqs"
        return "unknown"


class AWSLambdaProxyV2Request(BaseRequest):
    """
    AWS Lambda Proxy Integration v2 event.
    """

    def __init__(self, event, storage=None):
        super(AWSLambdaProxyV2Request, self).__init__(storage=storage)
        self.event = event
        self.rc = event.get("requestContext")

    @property
    def remote_addr(self):
        return self.rc.get("http", {}).get("sourceIp")

    @property
    def hostname(self):
        return self.rc.get("domainName")

    @property
    def method(self):
        return self.event.get("httpMethod")

    @property
    def referer(self):
        return self.get_raw_header("referer")

    @property
    def client_user_agent(self):
        return self.rc.get("http", {}).get("userAgent")

    @property
    def path(self):
        return self.event.get("rawPath")

    @property
    def query_string(self):
        return self.event.get("rawQueryString")

    @property
    def request_uri(self):
        return "?".join((self.event.get("rawPath"), self.event.get("rawQueryString")))

    @property
    def scheme(self):
        return self.event.get("headers", {}).get("x-forwarded-proto", "http")

    @property
    def server_port(self):
        return self.event.get("headers", {}).get("x-forwarded-port", "http")

    @property
    def remote_port(self):
        return None

    @property
    def view_params(self):
        return self.event.get("pathParameters")

    @property
    def body(self):
        isBase64Encoded = self.event.get("isBase64Encoded")
        body = self.event.get("body")
        if isBase64Encoded and body:
            return base64.b64decode(body)
        if is_string(body):
            return body
        return None

    @property
    def form_params(self):
        body = self.event.get("body")
        if isinstance(body, (Mapping, Iterable)):
            return body
        return None

    @property
    def query_params(self):
        params = self.event.get("multiValueQueryStringParameters", self.event.get("queryStringParameters"))
        return params if params is not None else dict()

    @property
    def cookies_params(self):
        return self.event.get("cookies")

    @property
    def raw_headers(self):
        return self.event.get("headers")


class AWSLambdaProxyV1Request(BaseRequest):
    """
    AWS Lambda Proxy Integration event.
    """

    def __init__(self, event, storage=None):
        super(AWSLambdaProxyV1Request, self).__init__(storage=storage)
        self.event = event
        self.rc = event.get("requestContext")

    @property
    def remote_addr(self):
        return self.rc.get("identity", {}).get("sourceIp")

    @property
    def hostname(self):
        return self.rc.get("domainName")

    @property
    def method(self):
        return self.event.get("httpMethod")

    @property
    def referer(self):
        return self.get_raw_header("referer")

    @property
    def client_user_agent(self):
        return self.rc.get("identity", {}).get("userAgent")

    @property
    def path(self):
        return self.event.get("path")

    @property
    def scheme(self):
        return self.event.get("headers", {}).get("X-Forwarded-Proto", "http")

    @property
    def server_port(self):
        return self.event.get("headers", {}).get("X-Forwarded-Port")

    @property
    def remote_port(self):
        # No remote port in the event
        return None

    @property
    def view_params(self):
        return self.event.get("pathParameters")

    @property
    def body(self):
        isBase64Encoded = self.event.get("isBase64Encoded")
        body = self.event.get("body")
        if isBase64Encoded and body:
            return base64.b64decode(body)
        if is_string(body):
            return body
        return None

    @property
    def form_params(self):
        body = self.event.get("body")
        if isinstance(body, (Mapping, Iterable)):
            return body
        return None

    @property
    def query_params(self):
        params = self.event.get("multiValueQueryStringParameters", self.event.get("queryStringParameters"))
        return params if params is not None else dict()

    @property
    def cookies_params(self):
        return None

    @property
    def raw_headers(self):
        # TODO header case
        return self.event.get("headers")


class AWSLambdaProxyV1Response(BaseResponse):

    def __init__(self, response):
        self.res = response

    @property
    def status_code(self):
        return self.res.get("statusCode")

    @property
    def content_type(self):
        # TODO header case
        return self.res.get("headers", {}).get("Content-Type")

    @property
    def content_length(self):
        # TODO header case
        cl = self.res.get("headers", {}).get("Content-Length")
        if cl is not None:
            try:
                return int(cl)
            except Exception:
                pass
        return None


class RecordRequestContextAWSLambda(RecordTransportMixin, RecordRequestContext):

    def pre(self, instance, args, kwars, options):
        event = AWSLambdaEvent(args[0])
        service = event.guess_service
        self.record_observation("lambda.events", service, 1)
        if service in ("api-gateway-rest", "api-gateway-http", "elastic-load-balancer"):
            version = event.get("version")
            if version == "2.0":
                self._store_request(AWSLambdaProxyV2Request(event))
            else:
                self._store_request(AWSLambdaProxyV1Request(event))
            return
        elif service in ("kinesis", "sqs"):
            for record in event.get("Records", []):
                transport = {
                    "type": "aws-{}".format(service),
                    "host": "{}.{}.amazonaws.com".format(service, record.get("awsRegion")),
                    "topic": record.get("eventSourceARN"),
                }
                self.record_transport("consumer", transport)
            self.storage.set_whitelist_match(True)
        else:
            self.storage.set_whitelist_match(True)


class RecordResponseAWSLambda(RuleCallback):

    INTERRUPTIBLE = False

    def _record_response(self, options):
        result = options.get("result")
        if result:
            response = AWSLambdaProxyV1Response(result)
            self.storage.store_response(response)

    def post(self, instance, args, kwargs, options):
        self._record_response(options)

    def failing(self, instance, args, kwargs, options):
        self._record_response(options)


class SqreenErrorPageAWSLambda(BaseSqreenErrorPage):

    def failing(self, instance, args, kwargs, options):
        exc_info = options.get("exc_info")
        ret = self.handle_exception(exc_info[1])
        if ret is not None:
            status_code, body, headers = ret
            resp = {
                "statusCode": status_code,
                "headers": headers,
                "isBase64Encoded": False,
                "body": body,
            }
            return {
                "status": "override",
                "new_return_value": resp,
            }


class ExecuteRunner(RuleCallback):

    INTERRUPTIBLE = False

    @property
    def whitelisted(self):
        # Always run this callback
        return False

    def post(self, instance, args, kwars, options):
        self._flush()

    def failing(self, instance, args, kwars, options):
        self._flush()

    def _flush(self):
        self.runner.handle_messages(block=False)
        self.runner.aggregate_observations()
        self.runner.publish_metrics()
        self.runner.deliverer.drain(resiliently=False)
        # the heartbeat notifies the end of the request
        self.runner.do_heartbeat()


class AWSLambdaFrameworkAdapter:

    def instrumentation_callbacks(self, runner, storage):
        # The module must be similar to the strategy MODULE_NAME
        module = "__main__" if sys.version_info[:2] != (3, 7) else "bootstrap"
        return [
            RecordRequestContextAWSLambda.from_rule_dict({
                "name": "ecosystem_aws_lambda_request_context",
                "rulespack_id": "ecosystem/framework",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "callbacks": {},
                "metrics": [
                    {
                        "kind": "Sum",
                        "name": "lambda.events",
                        "period": 60
                    }
                ],
                "priority": 20,
            }, runner, storage),
            FrameworkTransportCallback.from_rule_dict({
                "name": "ecosystem_aws_lambda_transport",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "callbacks": {},
                "priority": 90,
            }, runner, storage),
            BindingAccessorProvideData.from_rule_dict({
                "name": "ecosystem_aws_lambda_provide_data",
                "rulespack_id": "ecosystem/framework",
                "conditions": {
                    "pre": {
                        "%and": [
                            "#.request",
                        ]
                    },
                    "post": {
                        "%and": [
                            "#.response",
                        ]
                    },
                },
                "data": {
                    "values": [
                        ["pre", [
                            ["server.request.client_ip", "#.client_ip"],
                            ["server.request.method", "#.method"],
                            ["server.request.uri.raw", "#.request_uri"],
                            ["server.request.headers.no_cookies", "#.headers_no_cookies"],
                            ["server.request.cookies", "#.cookies_params"],
                            ["server.request.query", "#.query_params"],
                            ["server.request.body", "#.body_params"],
                            ["server.request.body.raw", "#.body"],
                            ["server.request.path_params", "#.view_params"],
                        ]],
                        ["post", [
                            ["server.response.status", "#.response.status_code"],
                            ["server.response.headers.no_cookies", "#.response.headers_no_cookies"],
                            ["server.response.body.raw", "#.response.body"],
                        ]]
                    ]
                },
                "block": True,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "priority": 80,
            }, runner, storage),
            RecordResponseAWSLambda.from_rule_dict({
                "name": "ecosystem_aws_lambda_record_response",
                "rulespack_id": "ecosystem/framework",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "priority": 90,
            }, runner, storage),
            SqreenErrorPageAWSLambda.from_rule_dict({
                "name": "ecosystem_aws_lambda_error_page",
                "rulespack_id": "ecosystem/framework",
                "block": True,
                "test": False,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "priority": 100,
            }, runner, storage),
            CountHTTPCodesCB.from_rule_dict({
                "name": "ecosystem_aws_lambda_legacy_http_code",
                "rulespack_id": "ecosystem/framework",
                "callbacks": {},
                "conditions": {
                    "failing": {
                        "%and": [
                            "#.response"
                        ]
                    },
                    "post": {
                        "%and": [
                            "#.response"
                        ]
                    },
                    "pre": {}
                },
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "metrics": [
                    {
                        "kind": "Sum",
                        "name": "http_code",
                        "period": 60
                    }
                ],
                "priority": 60,
            }, runner, storage),
            BindingAccessorCounter.from_rule_dict({
                "name": "ecosystem_aws_lambda_ba_normal_http_counter",
                "rulespack_id": "ecosystem/framework",
                "callbacks": {},
                "conditions": {
                    "failing": {
                        "%and": [
                            "#.response",
                            {
                                "%lt": [
                                    "#.response.status_code",
                                    400
                                ]
                            }
                        ]
                    },
                    "post": {
                        "%and": [
                            "#.response",
                            {
                                "%lt": [
                                    "#.response.status_code",
                                    400
                                ]
                            }
                        ]
                    },
                    "pre": {}
                },
                "data": {
                    "values": [
                        "#.client_ip",
                        "#.response.status_code",
                    ]
                },
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "metrics": [
                    {
                        "kind": "Sum",
                        "name": "ip-http_code",
                        "period": 60
                    }
                ],
                "priority": 60,
            }, runner, storage),
            BindingAccessorCounter.from_rule_dict({
                "name": "ecosystem_aws_lambda_ba_error_http_counter",
                "rulespack_id": "ecosystem/framework",
                "callbacks": {},
                "conditions": {
                    "failing": {
                        "%and": [
                            "#.response",
                        ]
                    },
                    "post": {
                        "%and": [
                            "#.response",
                            {
                                "%gte": [
                                    "#.response.status_code",
                                    400
                                ]
                            },
                            {
                                "%lt": [
                                    "#.response.status_code",
                                    600
                                ]
                            }
                        ]
                    },
                    "pre": {}
                },
                "data": {
                    "values": [
                        "#.client_ip",
                        "#.response.status_code",
                        "#.path"
                    ]
                },
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "metrics": [
                    {
                        "kind": "Sum",
                        "name": "ip-http_code-path",
                        "period": 60
                    }
                ],
                "priority": 60,
            }, runner, storage),
            ExecuteRunner.from_rule_dict({
                "name": "ecosystem_aws_lambda_execute_runner",
                "rulespack_id": "ecosystem/transport",
                "block": False,
                "test": False,
                "hookpoint": {
                    "klass": "{}::None".format(module),
                    "method": "handle_event_request",
                    "strategy": "aws_lambda",
                },
                "callbacks": {},
                "priority": 10,
            }, runner, storage),
        ]
