# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Matcher module."""

import re
from collections import defaultdict

from .utils import is_unicode


class Matcher(object):
    """Fast regex-like matcher."""

    __slots__ = ("patterns", "_regexes", "min_size")

    _STRING_OPTIONS = {
        "anywhere": ("", ""),
        "starts_with": ("^", ""),
        "ends_with": ("", "$"),
        "equals": ("^", "$"),
    }

    def __init__(self, patterns):
        self.patterns = patterns
        self._regexes = []
        self.min_size = None

        self._load_patterns(patterns)

    def _load_pattern(self, pattern):
        """Load a generic pattern object.

        Return a value (pattern, flags, size) where
        * pattern is the corresponding regex pattern
        * flags represent the bitwise flags of the regex
        * size is the minimum size of matching strings if it can be determined,
          None otherwise.
        """
        pattern_type = pattern["type"]
        value = pattern["value"]
        ignore_case = not pattern.get("case_sensitive", False)
        options = pattern.get("options", [])
        if pattern_type == "string":
            return self._load_string_pattern(
                pattern, value, ignore_case, options
            )
        elif pattern_type == "regexp":
            return self._load_regex_pattern(
                pattern, value, ignore_case, options
            )
        else:
            raise ValueError("unknown pattern type {!r}".format(pattern_type))

    def _load_string_pattern(self, pattern, value, ignore_case, options):
        """Load a string pattern object."""
        option = options[0] if options else "anywhere"
        if option not in self._STRING_OPTIONS:
            raise ValueError("unknown match function {!r}".format(option))
        re_start, re_end = self._STRING_OPTIONS[option]
        re_pattern = u"(?:{}{}{})".format(re_start, re.escape(value), re_end)
        re_flags = re.IGNORECASE if ignore_case else 0
        return re_pattern, re_flags, pattern.get("min_length", len(value))

    def _load_regex_pattern(self, pattern, value, ignore_case, options):
        """Load a regex pattern object."""
        re_flags = 0
        if ignore_case:
            re_flags |= re.IGNORECASE
        if "multiline" in options:
            re_flags |= re.MULTILINE
        return value, re_flags, pattern.get("min_length")

    def _load_patterns(self, patterns):
        """Load all patterns."""
        sized = True
        min_size = None
        re_pattern_map = defaultdict(list)
        for pattern in patterns:
            re_pattern, re_flags, size = self._load_pattern(pattern)
            re_pattern_map[re_flags].append(re_pattern)
            if not sized:
                continue
            if size is None:
                sized = False
            elif min_size is None or size < min_size:
                min_size = size
        self.min_size = min_size if sized else None
        self._regexes.extend(
            re.compile("|".join(re_patterns), re_flags)
            for re_flags, re_patterns in re_pattern_map.items()
        )

    def match(self, value):
        """Test if the string is matched by at least one of the patterns.

        This method accepts Python 2 str and unicode objects, and Python 3
        bytes and str objects.
        """
        # Correct encoding if possible and needed
        if not is_unicode(value):
            value = value.decode("utf-8", errors="replace")

        # Check length.
        if self.min_size is not None and len(value) < self.min_size:
            return False

        # Match regexes.
        for regex in self._regexes:
            if regex.search(value) is not None:
                return True

        return False
