# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
"""Sanitizer used to remove sensitive data from our payload"""

import logging
import re

from . import config
from .utils import HAS_TYPING, is_string, is_unicode

if HAS_TYPING:
    from typing import (
        AbstractSet,
        Any,
        FrozenSet,
        Iterable,
        Iterator,
        Mapping,
        MutableMapping,
        Pattern,
        Tuple,
    )
else:
    from collections import Iterable, Mapping


LOGGER = logging.getLogger(__name__)

_SANITIZER = None


def default_sensitive_keys():
    return frozenset([k.strip().lower() for k in config.CONFIG["STRIP_SENSITIVE_KEYS"].split(',')])


def default_sensitive_regex():
    # type: () -> Pattern[str]
    try:
        pattern = config.CONFIG["STRIP_SENSITIVE_REGEX"]
        return re.compile(pattern)
    except (TypeError, re.error):
        LOGGER.warning("Invalid regexp configuration %r, using default.", config.CONFIG["STRIP_SENSITIVE_REGEX"])
        pattern = config.CONFIG_DEFAULT_VALUE["STRIP_SENSITIVE_REGEX"]
        return re.compile(pattern)


def get_sanitizer(sensitive_keys=None, sensitive_regex=None):
    global _SANITIZER

    if not config.CONFIG["STRIP_SENSITIVE_DATA"]:
        return NoSanitizer()
    if _SANITIZER is None:
        sensitive_keys = sensitive_keys if sensitive_keys is not None else default_sensitive_keys()  # type: FrozenSet[str]
        sensitive_regex = sensitive_regex if sensitive_regex is not None else default_sensitive_regex()
        LOGGER.debug("Using sensitive keys %s", ", ".join(sensitive_keys))
        LOGGER.debug("Using sensitive regex %s", sensitive_regex.pattern)
        if not sensitive_keys or not sensitive_regex.pattern:
            LOGGER.warning("PII scrubbing might not be properly configured. More information on https://docs.sqreen.com/python/configuration/#customize-pii-scrubbing.")
        _SANITIZER = Sanitizer(sensitive_keys=sensitive_keys, sensitive_regex=sensitive_regex)
    return _SANITIZER


class NoSanitizer(object):

    def sanitize(self, data):
        return data, False

    def sanitize_attacks(self, attacks):
        return attacks

    def sanitize_exceptions(self, exceptions, sensitive_values):
        return exceptions


class Sanitizer(object):

    MASK = '<Redacted by Sqreen>'

    def __init__(self, sensitive_keys, sensitive_regex):
        # type: (AbstractSet[str], Pattern[str]) -> None
        self.sensitive_keys = sensitive_keys
        self.sensitive_regex = sensitive_regex

    def sanitize(self, data):
        # type: (Any) -> Tuple[Any, bool]
        """
        Sanitize sensitive data from an object. Return a 2-tuple with a sanitized
        copy of the data and a boolean indicating if some data was removed.
        """
        sensitive_values = False

        if is_string(data):
            if not is_unicode(data):
                data = data.decode("utf-8", errors="replace")
            if self.sensitive_regex.search(data):
                data = self.MASK
                sensitive_values = True
            return data, sensitive_values

        elif isinstance(data, Mapping):
            new_dict = {}
            for k, v in data.items():
                if is_string(k) and k.lower() in self.sensitive_keys:
                    new_dict[k] = self.MASK
                    sensitive_values = True
                else:
                    ret_data, ret_sensitive = self.sanitize(v)
                    new_dict[k] = ret_data
                    sensitive_values |= ret_sensitive
            return new_dict, sensitive_values

        elif isinstance(data, Iterable):
            new_list = []
            for v in data:
                ret_data, ret_sensitive = self.sanitize(v)
                new_list.append(ret_data)
                sensitive_values |= ret_sensitive
            return new_list, sensitive_values

        return data, sensitive_values

    def sanitize_attacks(self, attacks):
        # type: (Iterable[MutableMapping]) -> Iterator[MutableMapping]
        """
        Sanitize sensitive data from a list of attacks. Return the sanitized
        attacks.
        """
        for attack in attacks:
            infos = attack.get("infos")
            if infos is None:
                continue

            waf_data = infos.get("waf_data")
            if waf_data is not None:
                new_waf_data = []
                for item in waf_data:
                    filters = item.get("filter")
                    if filters is None:
                        continue
                    for filter_item in filters:
                        resolved_value = filter_item.get("resolved_value")
                        if is_string(resolved_value) and self.sensitive_regex.search(resolved_value):
                            filter_item["match_status"] = self.MASK
                            filter_item["resolved_value"] = self.MASK
                            continue
                        key_path = filter_item.get("key_path")
                        if isinstance(key_path, Iterable):
                            for key in key_path:
                                if is_string(key) and key.lower() in self.sensitive_keys:
                                    filter_item["match_status"] = self.MASK
                                    filter_item["resolved_value"] = self.MASK
                                    break
                    new_waf_data.append(item)
                infos["waf_data"] = new_waf_data
            else:
                attack["infos"], _ = self.sanitize(infos)
            yield attack

    def sanitize_exceptions(self, exceptions, sensitive_values):
        # type: (Iterable[Mapping], bool) -> Iterator[Mapping]
        """
        Sanitize sensitive data from a list of exceptions. Return the sanitized
        exceptions.
        """
        for exc in exceptions:
            infos = exc.get("infos")
            if infos is not None:
                # We know the request contains PII, never send args
                # TODO more fine grained filtering
                args = infos.get("args")
                if args is not None and sensitive_values:
                    infos.pop("args", None)

                waf_infos = infos.get("waf")
                if waf_infos is not None and sensitive_values:
                    waf_infos.pop("args", None)

            yield exc
