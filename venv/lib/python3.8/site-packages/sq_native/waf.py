# -*- coding: utf-8 -*-
# Copyright (c) 2016, 2017, 2018, 2019 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Higher-level In-App WAF Binding
"""
import json
import ctypes
import threading

from ._compat import UNICODE_CLASS
from ._ffi import PW_GOOD, PW_BLOCK, PW_MONITOR, PW_ERR_INVALID_CALL, \
        PW_ERR_TIMEOUT, pw_freeReturn, pw_initH, \
        pw_freeDiagnotics, pw_runH, pw_clearRuleH, pw_initAdditiveH, \
        pw_runAdditive, pw_clearAdditive
from .input import Input


class WAFReturn:
    """In-App WAF run return value."""

    def __init__(self, obj):
        self._obj = obj

    def __del__(self):
        if self._obj is None:
            return
        pw_freeReturn(self._obj)
        self._obj = None

    @property
    def error(self):
        """True if something went wrong during the run, the data field should
        be populated."""
        action = self.action
        return action is not None and action < PW_GOOD

    @property
    def block(self):
        """True if the request should be blocked."""
        return self.action == PW_BLOCK

    @property
    def report(self):
        """True if the request should be reported."""
        return self.action in (PW_BLOCK, PW_MONITOR)

    @property
    def timeout(self):
        """True if the In-App WAF timed out."""
        return self.action == PW_ERR_TIMEOUT

    @property
    def action(self):
        """Raw return value."""
        if self._obj is not None:
            return self._obj.action

    @property
    def data(self):
        """Raw data to report."""
        if self._obj is not None:
            return self._obj.data

    @property
    def perf_total_runtime(self):
        """WAF internal perf counter in micro seconds."""
        if self._obj is not None:
            return self._obj.perfTotalRuntime

    @property
    def perf_cache_hit_rate(self):
        """WAF internal cache hit counter."""
        if self._obj is not None:
            return self._obj.perfCacheHitRate

    @property
    def perf_data(self):
        """WAF internal perf data."""
        if self._obj is not None:
            return self._obj.perfData

    def __repr__(self):
        return "<WAFReturn block={0.block!r} report={0.report!r} error={0.error!r}>".format(self)


class WAFEngine:
    """
    In-App WAF engine interface.
    """

    def __init__(self, data):
        if isinstance(data, UNICODE_CLASS):
            data = data.encode("utf-8", errors="surrogatepass")
        diag_ptr = ctypes.c_char_p(None)
        try:
            self.handle = pw_initH(data, None, ctypes.byref(diag_ptr))
            if self.handle is None:
                if diag_ptr:
                    diag = diag_ptr.value.decode("utf-8")
                else:
                    diag = "unexpected error during WAF initialization"
                raise ValueError(diag)
        finally:
            if diag_ptr:
                pw_freeDiagnotics(diag_ptr)

    def create_context(self):
        """Start a new In-App WAF context for a request allowing to provide
        parameters progressively.
        """
        return WAFContext(self)

    def run(self, parameters, budget):
        """Run the In-App WAF on the given parameters."""
        if not isinstance(parameters, Input):
            parameters = Input.from_python(parameters)
        elif parameters.owned:
            raise ValueError("cannot use already submitted parameters")

        return WAFReturn(pw_runH(
            self.handle, parameters._obj, ctypes.c_size_t(budget)
        ))

    def __del__(self):
        handle = getattr(self, "handle", None)
        if handle is not None:
            pw_clearRuleH(handle)
            self.handle = None


class WAFContext:
    """In-App WAF request context."""

    def __init__(self, engine):
        # It is very important to keep a reference to the engine from the
        # context because it will prevent the garbage collertor to free
        # the engine while there are active contexts.
        self.engine = engine
        self.handle = pw_initAdditiveH(engine.handle)
        self.lock = threading.Lock()
        if self.handle is None:
            raise RuntimeError("unexpected error while creating a WAF context")

    def run(self, parameters, budget):
        """Run the In-App WAF with new parameters.
        """
        if not isinstance(parameters, Input):
            parameters = Input.from_python(parameters)
        elif parameters.owned:
            raise ValueError("cannot use already submitted parameters")

        with self.lock:
            ret = WAFReturn(pw_runAdditive(
                self.handle, parameters._obj, ctypes.c_size_t(budget)
            ))
            if ret.action not in (PW_ERR_INVALID_CALL, PW_ERR_TIMEOUT):
                parameters.owned = True
            return ret

    def __del__(self):
        if self.handle is not None:
            pw_clearAdditive(self.handle)
            self.handle = None
