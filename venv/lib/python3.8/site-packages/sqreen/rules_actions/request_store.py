# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Save to the request store.
"""


class RequestStoreMixin(object):
    """
    Mixin for rule callbacks to alter the request store.
    """

    def action_processor(self, result_action, options):
        """
        Save data to the request store from the callback return value.
        """
        result_action = super(RequestStoreMixin, self).action_processor(result_action, options)
        if result_action is None:
            return
        # Update the request store
        data = result_action.get("request_store")
        if data:
            self.storage.update_request_store(**data)
        return result_action
