# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
from ...frameworks.django_framework import DjangoRequest
from ...runtime_storage import runtime
from .base import BaseMiddleware


class DjangoMiddleware(BaseMiddleware):
    """ Wrap a RuleCallback and alias its methods to django middleware methods.
    Pre is mapped to process_view, post is mapped to process_reponse and
    failig is mapped to process_exception
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """ Call wrapped_callback.pre, raise AttackBlock if needed.
        Django pre callbacks will receive these arguments:
        (None, request, view_func, view_args, view_kwargs)
        """
        self.strategy.before_hook_point()
        transaction = request.__sqreen_transaction = self.create_transaction()
        args = (request, view_func, view_args, view_kwargs)

        self.execute_pre_callbacks(transaction, args)

    def process_response(self, request, response):
        """ Call wrapped_callback.post, raise AttackBlock if needed or returns
        the response passed as input.
        Django post callbacks will receive these arguments:
        (None, response, request)
        """
        # Record request if we don't have one yet
        runtime.store_request_default(DjangoRequest(request))

        transaction = getattr(request, "__sqreen_transaction", None)
        if transaction is None:
            transaction = request.__sqreen_transaction = self.create_transaction()

        # Execute pre_callbacks if the response is a 404 because the callback
        # process_view was not called by Django
        if response.status_code == 404:
            args = (request, None, None, None)
            self.execute_pre_callbacks(transaction, args)
        args = (request,)
        return self.execute_post_callbacks(transaction, response, args)

    def process_exception(self, request, exception):
        """ Call wrapped_callback.failing, always return None.
        Django failing callbacks will receive these arguments:
        (None, exception, request)
        """
        transaction = getattr(request, "__sqreen_transaction", None)
        if transaction is None:
            transaction = request.__sqreen_transaction = self.create_transaction()
        args = (request,)

        # Record request if we don't have one yet
        runtime.store_request_default(DjangoRequest(request))

        self.execute_failing_callbacks(transaction, exception, args)
