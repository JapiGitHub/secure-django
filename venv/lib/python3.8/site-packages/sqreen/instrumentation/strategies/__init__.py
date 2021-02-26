# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Hijacking strategies
"""

from ...utils import HAS_ASYNCIO
from .aws_lambda import AWSLambdaStrategy
from .base import BaseStrategy
from .dbapi2 import DBApi2Strategy
from .django_strategy import DjangoStrategy
from .flask_strategy import FlaskStrategy
from .import_hook import ImportHookStrategy
from .lxml_strategy import LXMLResolverStrategy
from .psycopg2_strategy import Psycopg2Strategy
from .pyramid_strategy import PyramidStrategy
from .wsgi_strategy import (
    WSGIFactoryStrategy,
    WSGIReceiverStrategy,
    WSGIStrategy,
)

if HAS_ASYNCIO:
    from .aiohttp_strategy import AioHTTPHookStrategy, AioHTTPInstallStrategy
    from .async_event_loop import AsyncEventLoopStrategy
    from .async_import_hook import AsyncImportHookStrategy

__all__ = [
    "AWSLambdaStrategy",
    "AioHTTPHookStrategy",
    "AioHTTPInstallStrategy",
    "AsyncEventLoopStrategy",
    "AsyncImportHookStrategy",
    "BaseStrategy",
    "DBApi2Strategy",
    "DjangoStrategy",
    "FlaskStrategy",
    "LXMLResolverStrategy",
    "ImportHookStrategy",
    "Psycopg2Strategy",
    "PyramidStrategy",
    "WSGIFactoryStrategy",
    "WSGIReceiverStrategy",
    "WSGIStrategy"
]
