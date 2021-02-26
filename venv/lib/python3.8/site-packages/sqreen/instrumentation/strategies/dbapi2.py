# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" DBApi2 strategy and custom connection and cursor classes
"""
import functools
import logging

from ..._vendors.wrapt import FunctionWrapper, ObjectProxy
from ..hook_point import hook_point_wrapper
from .base import BaseStrategy

LOGGER = logging.getLogger(__name__)


class CustomCursorBase(ObjectProxy):
    """ CustomCursor proxy, it proxy a real Cursor of a DBApi2
    module, instrument all known DBApi2 methods.
    """

    def callproc(self, *args, **kwargs):
        return self._self_sqreen_wrapper("callproc")(
            self.__wrapped__.callproc,
            self.__wrapped__,
            args,
            kwargs
        )

    def execute(self, *args, **kwargs):
        return self._self_sqreen_wrapper("execute")(
            self.__wrapped__.execute,
            self.__wrapped__,
            args,
            kwargs
        )

    def executemany(self, *args, **kwargs):
        return self._self_sqreen_wrapper("executemany")(
            self.__wrapped__.executemany,
            self.__wrapped__,
            args,
            kwargs
        )

    def executescript(self, *args, **kwargs):
        return self._self_sqreen_wrapper("executescript")(
            self.__wrapped__.executescript,
            self.__wrapped__,
            args,
            kwargs
        )

    def close(self, *args, **kwargs):
        return self._self_sqreen_wrapper("close")(
            self.__wrapped__.close,
            self.__wrapped__,
            args,
            kwargs
        )

    def fetchone(self, *args, **kwargs):
        return self._self_sqreen_wrapper("fetchone")(
            self.__wrapped__.fetchone,
            self.__wrapped__,
            args,
            kwargs
        )

    def fetchmany(self, *args, **kwargs):
        return self._self_sqreen_wrapper("fetchmany")(
            self.__wrapped__.fetchmany,
            self.__wrapped__,
            args,
            kwargs
        )

    def fetchall(self, *args, **kwargs):
        return self._self_sqreen_wrapper("fetchall")(
            self.__wrapped__.fetchall,
            self.__wrapped__,
            args,
            kwargs
        )

    def nextstep(self, *args, **kwargs):
        return self._self_sqreen_wrapper("nextstep")(
            self.__wrapped__.nextstep,
            self.__wrapped__,
            args,
            kwargs
        )

    def setinputsize(self, *args, **kwargs):
        return self._self_sqreen_wrapper("setinputsize")(
            self.__wrapped__.setinputsize,
            self.__wrapped__,
            args,
            kwargs
        )

    def setoutputsize(self, *args, **kwargs):
        return self._self_sqreen_wrapper("setoutputsize")(
            self.__wrapped__.setoutputsize,
            self.__wrapped__,
            args,
            kwargs
        )


class CustomConnectionBase(ObjectProxy):
    """ CustomConnection proxy, it proxy a real Connection of a DBApi2
    module, instrument all DBApi2 known methods and returns
    CustomCursor when callin the cursor method.
    """

    def close(self, *args, **kwargs):
        return self._self_sqreen_wrapper("close")(
            self.__wrapped__.close,
            self.__wrapped__,
            args,
            kwargs
        )

    def commit(self, *args, **kwargs):
        return self._self_sqreen_wrapper("commit")(
            self.__wrapped__.commit,
            self.__wrapped__,
            args,
            kwargs
        )

    def rollback(self, *args, **kwargs):
        return self._self_sqreen_wrapper("rollback")(
            self.__wrapped__.rollback,
            self.__wrapped__,
            args,
            kwargs
        )

    def cursor(self, *args, **kwargs):
        """ Instantiate a real cursor, proxy it via CustomCursor.
        """
        return self._self_sqreen_cursor_class(
            self.__wrapped__.cursor(*args, **kwargs))


class CustomConnectionExtendedBase(CustomConnectionBase):
    """SQLite3 extends the DBApi2 Connection object with some proxy functions
    to Cursor.
    """

    def execute(self, *args, **kwargs):
        return self._self_sqreen_wrapper("execute")(
            self.__wrapped__.execute,
            self.__wrapped__,
            args,
            kwargs
        )

    def executemany(self, *args, **kwargs):
        return self._self_sqreen_wrapper("executemany")(
            self.__wrapped__.executemany,
            self.__wrapped__,
            args,
            kwargs
        )

    def executescript(self, *args, **kwargs):
        return self._self_sqreen_wrapper("executescript")(
            self.__wrapped__.executescript,
            self.__wrapped__,
            args,
            kwargs
        )


def custom_cursor_class(inner_wrapper, module_path):
    class CustomCursor(CustomCursorBase):
        _self_sqreen_wrapper = functools.partial(
            inner_wrapper, "{}::Cursor".format(module_path))
    return CustomCursor


def custom_connect(inner_wrapper, module_path, original_connect):
    """ Replacement to the connect function of a DBApi2 module. It will
    instantiate a connection via the original connect function and proxy it
    via CustomConnection defined earlier.
    """

    cursor_class = custom_cursor_class(inner_wrapper, module_path)
    connection_wrapper = functools.partial(
        inner_wrapper, "{}::Connection".format(module_path))

    class CustomConnection(CustomConnectionBase):
        _self_sqreen_cursor_class = cursor_class
        _self_sqreen_wrapper = connection_wrapper

    class CustomConnectionExtended(CustomConnectionExtendedBase):
        _self_sqreen_cursor_class = cursor_class
        _self_sqreen_wrapper = connection_wrapper

    def wrapper(wrapped, instance, args, kwargs):
        conn = inner_wrapper(module_path, "connect")(wrapped, None, args, kwargs)
        if hasattr(conn, "execute"):
            # SQLite 3 has some extensions to DBApi2
            return CustomConnectionExtended(conn)
        return CustomConnection(conn)

    return FunctionWrapper(original_connect, wrapper)


class DBApi2Strategy(BaseStrategy):
    """ Strategy for DBApi2 drivers.

    It's different from the SetAttrStrategy and requires special care in
    hook_module and hook_name.
    DBApi2 tries to hook on 'connect' method of DBApi2 compatible driver.
    In order to do so, it needs the module name where 'connect' is available. It
    must be the first part of hook_module, for example in sqlite3, it will be
    'sqlite3'.

    The hook_module could then contains either '::Cursor' for hooking on
    cursor methods or '::Connection' for hooking on connection methods.
    The hook_name will then specify which method it will hook on.

    For example with sqlite3, the tuple ('sqlite3::Connection', 'execute') will
    reference the execute method on a sqlite3 connection.
    In the same way, the tuple ('sqlite3::Cursor', 'execute') will reference
    the execute method on a sqlite3 cursor.

    It will works the same way for all DBApi2 drivers, even with psycopg2
    where cursor class is actually defined as 'psycopg2.extensions.cursor',
    'psycopg2::Cursor' will correctly reference all psycopg2 cursor methods.
    """

    def __init__(self, *args, **kwargs):
        super(DBApi2Strategy, self).__init__(*args, **kwargs)
        self.module_path = self.strategy_id
        self.import_hook.register_patcher(
            self.module_path, None, "connect", self.import_hook_callback
        )

    def import_hook_callback(self, original):
        """ Monkey-patch the object located at hook_class.hook_name on an
        already loaded module
        """
        _hook_point = functools.partial(hook_point_wrapper, self)
        return custom_connect(_hook_point, self.module_path, original)

    @staticmethod
    def get_strategy_id(callback):
        """ Returns the module part of hook_module (without everything after
        ::) as identifier for this strategy. Multiple hooks on sqlite3* should
        be done in this strategy.
        """
        # Check if the klass is part module and part klass name
        if "::" in callback.hook_module:
            return callback.hook_module.split("::", 1)[0]
        else:
            return callback.hook_module
