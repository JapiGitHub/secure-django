# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#


class RequestPrefixListFilter(object):
    """ Matcher class for request path prefixes
    """

    def __init__(self, prefixes=None):
        if prefixes is None:
            prefixes = []
        self.reset(prefixes)

    def reset(self, prefixes):
        """ Reset the list of request path prefixes
        """
        self._prefixes = list(prefixes)

    def __iter__(self):
        return iter(self._prefixes)

    def match(self, path):
        """ Check if a request path is matched by a prefix

        Return the first matching prefix, or None if the request path does not
        start with any recorded prefix.
        """
        if not self._prefixes:
            return
        for prefix in self._prefixes:
            if path.startswith(prefix):
                return prefix

    def __repr__(self):
        return "{}({!r})".format(self.__class__.__name__, self._prefixes)

    def __str__(self):
        return ", ".join(self)
