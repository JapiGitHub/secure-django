# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#

import logging

from ..exceptions import InvalidArgument
from ..rules import RuleCallback
from ..rules_actions import RecordAttackMixin
from ..utils import Mapping, is_string

LOGGER = logging.getLogger(__name__)


class ExtensionPassthruCB(RecordAttackMixin, RuleCallback):
    """Daemon callback that just raises with the data the extension gives"""

    INTERRUPTIBLE = False

    def __init__(self, *args, **kwargs):
        super(ExtensionPassthruCB, self).__init__(*args, **kwargs)

        if not self.attack_render_info or not isinstance(self.attack_render_info, Mapping):
            msg = "Invalid data type received for 'attack_render_info': {}"
            raise InvalidArgument(msg.format(type(self.attack_render_info)))

    # info keys are stored like this in the rule:
    # rule = {
    #   "hookpoint": {
    #     "attack_render_info": {
    #       "pre": { <- upon data receiving, will generate attack with this info
    #         "found": "#.cargs[0]"
    #       }
    #     }
    #   }
    #   "callbacks": { <- determines what gets sent to the daemon
    #     "pre": [
    #       "#.request_params",
    #       "#.cargs[0]",
    #       "javascript code" <- extension ignores last element
    #     ]
    #   }
    # }
    def __fetch_render_info(self, cb_name):
        ret = self.attack_render_info.get(cb_name)
        if not isinstance(ret, dict) or \
                any([not is_string(k) or not is_string(v)
                     for (k, v) in ret.items()]):
            LOGGER.warning("Invalid attack rendering infos spec: %s", ret)
            return {}
        return ret

    def __build_info(self, attack_render_info):
        # map ba expr -> its resolution, as calculated by ext
        cmd_args = self.storage.get_cmd_arguments()
        if cmd_args is None:
            cmd_args = {}

        return {
            k: cmd_args.get(ba_expr) for (k, ba_expr) in attack_render_info.items()
        }

    def pre(self, instance, args, kwargs, options):
        attack_render_info = self.__fetch_render_info('pre')
        attack_rec = self.__build_info(attack_render_info)

        status = attack_rec.pop("__status_override", "raise")
        if len(attack_rec) != 0:
            self.record_attack(attack_rec)

        return {'status': status}

    def post(self, instance, args, kwargs, options):
        LOGGER.error("Called unsupported 'post' method")
        return

    def failing(self, instance, args, kwargs, options):
        LOGGER.error("Called unsupported 'failing' method")
        return
