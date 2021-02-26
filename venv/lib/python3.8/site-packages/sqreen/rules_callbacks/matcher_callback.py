# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base class for matcher based rules
"""
from logging import getLogger

from ..exceptions import InvalidArgument
from ..matcher import Matcher
from ..rules import RuleCallback
from ..utils import Mapping

LOGGER = getLogger(__name__)


class MatcherRule(RuleCallback):
    """ Base class for matcher based rules.
    The valid matcher syntax is described here:
    https://github.com/sqreen/Wiki/wiki/String-matcher
    """

    def __init__(self, *args, **kwargs):
        super(MatcherRule, self).__init__(*args, **kwargs)

        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        try:
            raw_patterns = self.data["values"]
        except KeyError:
            msg = "No key 'values' in data (had {})"
            raise InvalidArgument(msg.format(self.data.keys()))

        self.matcher = Matcher(raw_patterns)

    def match(self, string):
        """ Check if string match one of rule pattern
        """
        return self.matcher.match(string)
