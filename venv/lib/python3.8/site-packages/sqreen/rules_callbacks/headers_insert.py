# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Insert X-Protected-By header
"""
import logging

from ..exceptions import InvalidArgument
from ..rules import RuleCallback
from ..utils import Mapping, cached_property, itervalues

LOGGER = logging.getLogger(__name__)


def convert_to_str(headers):
    """ Encode a list of headers tuples into latin1
    """
    for header_name, header_value in headers:
        header_name = str(
            header_name.encode("latin-1", errors="replace").decode("latin-1")
        )
        header_value = str(
            header_value.encode("latin-1", errors="replace").decode("latin-1")
        )
        yield header_name, header_value


class BaseHeadersInsertCB(RuleCallback):
    """ Base class for header insertion callbacks
    """

    def __init__(self, *args, **kwargs):
        super(BaseHeadersInsertCB, self).__init__(*args, **kwargs)

        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

    @cached_property
    def headers(self):
        return {
            name.lower(): (name, value)
            for name, value in convert_to_str(self.data.get("values", []))
        }


class HeadersInsertCB(BaseHeadersInsertCB):
    """ Callback that add the custom sqreen header in WSGI
    """

    def pre(self, instance, args, kwargs, options):
        new_args = list(args)
        headers_to_add = dict(self.headers)
        new_headers = []
        current_headers = args[1]

        # Replace current headers
        new_headers.extend([headers_to_add.pop(n.lower(), (n, v))
                            for n, v in current_headers])

        # Add remaining headers
        new_headers.extend(itervalues(headers_to_add))

        new_args[1] = new_headers
        return {"status": "modify_args", "args": [new_args, kwargs]}
