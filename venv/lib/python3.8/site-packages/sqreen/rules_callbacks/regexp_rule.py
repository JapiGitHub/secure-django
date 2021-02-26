# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Base class for regexp based rules
"""
import re
from logging import getLogger

from ..exceptions import InvalidArgument
from ..rules import RuleCallback
from ..utils import Mapping

LOGGER = getLogger(__name__)


class RegexpRule(RuleCallback):
    """ Base class for callback using regexp data to detect attacks.
    Provides the match_regexp method to quickly check if a string match
    one of the regexp data values.
    """

    def __init__(self, *args, **kwargs):
        super(RegexpRule, self).__init__(*args, **kwargs)

        self.patterns = []
        self._prepare_patterns()

    def _prepare_patterns(self):
        """ Precompile regexp patterns
        """
        if not isinstance(self.data, Mapping):
            msg = "Invalid data type received: {}"
            raise InvalidArgument(msg.format(type(self.data)))

        try:
            raw_patterns = self.data["values"]
        except KeyError:
            msg = "No key 'values' in data (had {})"
            raise InvalidArgument(msg.format(self.data.keys()))

        for pattern in raw_patterns:
            try:
                self.patterns.append(re.compile(pattern, re.IGNORECASE))
            except (re.error, AssertionError):
                LOGGER.warning("%s fails to compile", pattern, exc_info=True)

    def match_regexp(self, string):
        """ Check if string matches one of rule pattern
        """
        for pattern in self.patterns:
            if pattern.search(string):
                # Returns the string pattern that matched
                return pattern.pattern
