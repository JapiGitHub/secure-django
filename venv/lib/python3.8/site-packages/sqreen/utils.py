# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Various utils
"""
import datetime
import json
import sys
import types
from collections import deque
from inspect import isclass
from itertools import islice
from logging import getLogger
from operator import methodcaller

from ._vendors.ipaddress import (  # type: ignore
    ip_address as _ip_address,
    ip_network as _ip_network,
)

if sys.version_info >= (3, 5):
    from typing import (
        Any,
        Callable,
        Dict,
        Iterable,
        List,
        Mapping,
        Optional,
        Set,
        Tuple,
    )

    HAS_TYPING = True

    ConvertFunc = Callable[[Any], Optional[str]]

else:
    from collections import Iterable, Mapping

    HAS_TYPING = False

LOGGER = getLogger(__name__)

HAS_ASYNCIO = sys.version_info >= (3, 4)

NONE_TYPE = type(None)

ZERO_TD = datetime.timedelta(0)

if sys.version_info[0] < 3:
    ALL_STRING_CLASS = basestring  # noqa
    STRING_CLASS = str
    UNICODE_CLASS = unicode  # noqa

    def viewkeys(d, **kwargs):
        return d.viewkeys(**kwargs)

    def iterkeys(d, **kwargs):
        return d.iterkeys(**kwargs)

    def itervalues(d, **kwargs):
        return d.itervalues(**kwargs)

    def create_bound_method(func, obj):
        return types.MethodType(func, obj, obj.__class__)

    class FixedOffsetTZ(datetime.tzinfo):
        """Fixed offset in minutes east from UTC."""

        def __init__(self, offset, name):
            self.__offset = datetime.timedelta(minutes=offset)
            self.__name = name

        def utcoffset(self, dt):
            return self.__offset

        def tzname(self, dt):
            return self.__name

        def dst(self, dt):
            return ZERO_TD

    UTC = FixedOffsetTZ(0, "UTC")

else:
    ALL_STRING_CLASS = str
    STRING_CLASS = str
    UNICODE_CLASS = str

    def viewkeys(d, **kwargs):
        return d.keys(**kwargs)

    iterkeys = viewkeys

    def itervalues(d, **kwargs):
        return d.values(**kwargs)

    create_bound_method = types.MethodType

    FixedOffsetTZ = datetime.timezone

    UTC = datetime.timezone.utc


def is_string(value):  # type: (Any) -> bool
    """ Check if a value is a valid string, compatible with python 2 and python 3

    >>> is_string('foo')
    True
    >>> is_string(u'✌')
    True
    >>> is_string(42)
    False
    >>> is_string(('abc',))
    False
    """
    return isinstance(value, ALL_STRING_CLASS)


def is_unicode(value):  # type: (Any) -> bool
    """ Check if a value is a valid unicode string, compatible with python 2 and python 3

    >>> is_unicode(u'foo')
    True
    >>> is_unicode(u'✌')
    True
    >>> is_unicode(b'foo')
    False
    >>> is_unicode(42)
    False
    >>> is_unicode(('abc',))
    False
    """
    return isinstance(value, UNICODE_CLASS)


def to_latin_1(value):  # type: (str) -> bytes
    """ Return the input string encoded in latin1 with replace mode for errors
    """
    return value.encode("latin-1", "replace")


def is_json_serializable(value):  # type: (Any) -> bool
    """ Check that a single value is json serializable
    """
    return isinstance(value, (ALL_STRING_CLASS, NONE_TYPE, bool, int, float))  # type: ignore


def to_unicode_safe(value):  # type: (Any) -> Optional[str]
    """ Safely convert a value to a unicode string.
    """
    if value is None:
        return value
    # If value is a byte string (string without encoding)
    # Try to decode it as unicode, this operation will
    # always succeed because non UTF-8 characters will
    # get replaced by the UTF-8 replacement character.
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    # If the value is not already a unicode string
    # Try to convert it to a string
    # by calling the standard Python __str__ method on
    # the value.
    elif not is_unicode(value):
        value = STRING_CLASS(value)
        # In Python 2.7, the returned value has no encoding
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
    # Value is already a unicode string
    return value


# Sentry SDK
def configure_sentry_ignore_errors():
    """ Ignore all logging messages from sqreen.* loggers, effectively
    disabling sentry_sdk to log sqreen log messages as breadcrumbs
    """
    try:
        from sentry_sdk.scope import add_global_event_processor
    except ImportError:
        return

    try:
        @add_global_event_processor
        def ignore_sqreen_errors(event, hint):
            try:
                if event.get("logger", "").startswith("sqreen"):
                    return None
                return event
            except Exception:
                pass
    except Exception:
        LOGGER.warning("Error while configuring sentry_sdk", exc_info=True)


###
# Raven configuration
###


def _raven_ignoring_handler(logger, *args, **kwargs):
    """ Ignore all logging messages from sqreen.* loggers, effectively
    disabling raven to log sqreen log messages as breadcrumbs
    """
    try:
        if logger.name.startswith("sqreen"):
            return True
    except Exception:
        LOGGER.warning("Error in raven ignore handler", exc_info=True)


def configure_raven_breadcrumbs():
    """ Configure raven breadcrumbs logging integration if raven is present
    """
    try:
        from raven import breadcrumbs  # type: ignore
    except ImportError:
        return

    # Register our logging handler to stop logging sqreen log messages
    # as breadcrumbs
    try:
        breadcrumbs.register_logging_handler(_raven_ignoring_handler)
    except Exception:
        LOGGER.warning("Error while configuring breadcrumbs", exc_info=True)


###
# NewRelics
###

def configure_newrelics_ignore_exception():
    """ Check if newrelics package is here, and disable Sqreen Exception
    """

    try:
        import newrelic.agent  # type: ignore
    except ImportError:
        return

    try:
        newrelic.agent.global_settings().error_collector.ignore_errors.extend(['sqreen.exceptions:RequestBlocked',
                                                                               'sqreen.exceptions:AttackBlocked',
                                                                               'sqreen.exceptions:ActionBlock',
                                                                               'sqreen.exceptions:ActionRedirect'])
    except Exception:
        LOGGER.warning("Error while configuring newrelics", exc_info=True)


###
# JSON Encoder
###


def qualified_class_name(obj):  # type: (Any) -> str
    """ Return the full qualified name of the class name of obj in form of
    `full_qualified_module.class_name`
    """
    if isclass(obj):
        instance_class = obj
    else:
        instance_class = obj.__class__

    return ".".join([instance_class.__module__, instance_class.__name__])


def django_user_conversion(obj):  # type: (Any) -> Optional[str]
    """ Convert a Django user either by returning USERNAME_FIELD or convert
    it to str.
    """
    if hasattr(obj, "USERNAME_FIELD"):
        return to_unicode_safe(getattr(obj, getattr(obj, "USERNAME_FIELD"), None))
    else:
        return UNICODE_CLASS(obj)


def psycopg_composable_conversion(obj, max_depth=64):  # type: (Any, int) -> str
    """ Best effort psycopg2 Composable string convertion.
    """
    if max_depth == 0:
        raise ValueError("Max depth reached while converting a psycopg2.sql.Composable")
    if hasattr(obj, "strings"):  # psycopg2.sql.Identifier
        # escaping is explained on https://www.postgresql.org/docs/current/sql-syntax-lexical.html#
        return ".".join(json.dumps(i).replace('\\"', '""') for i in obj.strings if isinstance(i, str))
    if hasattr(obj, "wrapped"):  # psycopg2.sql.Literal
        if isinstance(obj.wrapped, str):
            return "'{}'".format(obj.wrapped.replace("'", "''"))
        return repr(obj.wrapped)
    elif hasattr(obj, "__iter__"):  # psycopg2.sql.Composed
        return "".join(psycopg_composable_conversion(i, max_depth=max_depth - 1) for i in obj)
    return obj.as_string(None)


OBJECT_STRING_MAPPING = {
    "bson.objectid.ObjectId": UNICODE_CLASS,
    # Convert datetime to isoformat, compatible with Node Date()
    "datetime.datetime": methodcaller("isoformat"),
    "django.contrib.auth.models.AbstractUser": django_user_conversion,
    "os.PathLike": methodcaller("__fspath__"),
    "pathlib.PurePath": UNICODE_CLASS,
    "psycopg2.sql.Composable": psycopg_composable_conversion,
    "sqlalchemy.sql.elements.ClauseElement": UNICODE_CLASS,
    "sqreen._vendors.ipaddress.IPv4Address": UNICODE_CLASS,
    "sqreen._vendors.ipaddress.IPv6Address": UNICODE_CLASS,
}  # type: Dict[str, ConvertFunc]


def convert_to_string(obj, object_string_mapping=OBJECT_STRING_MAPPING):
    # type: (Any, Mapping[str, ConvertFunc]) -> Optional[str]
    """ Return a string representation for objects that are known to safely convert to string.
    """
    if type(obj) == type:
        instance_class = obj
    else:
        instance_class = obj.__class__

    # Manually do isinstance without needed to have a reference to the class
    for klass in instance_class.__mro__:
        qualified_name = qualified_class_name(klass)
        func = object_string_mapping.get(qualified_name)
        if func is not None:
            try:
                return func(obj)
            except Exception:
                LOGGER.warning("Error converting an instance of type %r", obj.__class__, exc_info=True)
    raise ValueError("cannot convert safely {} to string".format(instance_class))


class CustomJSONEncoder(json.JSONEncoder):
    MAPPING = OBJECT_STRING_MAPPING

    def default(self, obj):  # type: (Any) -> Optional[str]
        """ Return the repr of unkown objects
        """
        try:
            return convert_to_string(obj, object_string_mapping=self.MAPPING)
        except ValueError:
            # If we don't, or if we except, fallback on repr
            return repr(obj)


def ip_address(address):
    return _ip_address(UNICODE_CLASS(address))


def ip_network(address, strict=True):
    return _ip_network(UNICODE_CLASS(address), strict=strict)


def truncate_time(dt=None, round_to=60):  # type: (Optional[datetime.datetime], int) -> datetime.datetime
    """Return a datetime rounded to the previous given second interval."""
    if dt is None:
        dt = now()
    dt = dt.replace(microsecond=0)
    if dt.tzinfo is None:
        naive_dt = dt
    else:
        offset = dt.utcoffset()
        if offset is None:
            offset = ZERO_TD
        naive_dt = dt.replace(tzinfo=None) - offset
    seconds = (naive_dt - naive_dt.min).total_seconds()
    return dt - datetime.timedelta(seconds=seconds % round_to)


def flatten(iterable, max_iterations=1000):
    # type: (Iterable, int) -> Tuple[List, List]
    """Return the list of keys and values of iterable and nested iterables."""
    iteration = 0
    keys = []  # type: List[Any]
    values = []  # type: List[Any]
    remaining_iterables = deque([iterable], maxlen=max_iterations)
    seen_iterables = set()  # type: Set[int]

    while remaining_iterables:

        iteration += 1
        # If we have a very big or nested iterable, returns False.
        if iteration >= max_iterations:
            break

        iterable = remaining_iterables.popleft()
        id_iterable = id(iterable)
        # Protection against recursive objects
        if id_iterable in seen_iterables:
            continue
        seen_iterables.add(id_iterable)

        # If we get an iterable, add it to the list of remaining iterables.
        if isinstance(iterable, Mapping):
            keys.extend(islice(iterkeys(iterable), max_iterations))
            remaining_iterables.extend(islice(itervalues(iterable), max_iterations))
        elif isinstance(iterable, (list, tuple)):
            remaining_iterables.extend(islice(iter(iterable), max_iterations))
        else:
            values.append(iterable)

    return keys, values


def naive_dt_to_utc(dt):  # type: (datetime.datetime) -> datetime.datetime
    """Convert naive datetime to timezone aware datetime.
    By default, we consider all naive datetime to be in UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def now():  # type: () -> datetime.datetime
    """ Return the current UTC time.
    """
    return datetime.datetime.now(UTC)


# Helpers for parsing the result of isoformat() from
# https://github.com/python/cpython/blob/3.8/Lib/datetime.py
def _parse_isoformat_date(dtstr):
    # It is assumed that this function will only be called with a
    # string of length exactly 10, and (though this is not used) ASCII-only
    year = int(dtstr[0:4])
    if dtstr[4] != '-':
        raise ValueError('Invalid date separator: %s' % dtstr[4])

    month = int(dtstr[5:7])

    if dtstr[7] != '-':
        raise ValueError('Invalid date separator')

    day = int(dtstr[8:10])

    return [year, month, day]


def _parse_hh_mm_ss_ff(tstr):
    # Parses things of the form HH[:MM[:SS[.fff[fff]]]]
    len_str = len(tstr)

    time_comps = [0, 0, 0, 0]
    pos = 0
    for comp in range(0, 3):
        if (len_str - pos) < 2:
            raise ValueError('Incomplete time component')

        time_comps[comp] = int(tstr[pos:pos + 2])

        pos += 2
        next_char = tstr[pos:pos + 1]

        if not next_char or comp >= 2:
            break

        if next_char != ':':
            raise ValueError('Invalid time separator: %c' % next_char)

        pos += 1

    if pos < len_str:
        if tstr[pos] != '.':
            raise ValueError('Invalid microsecond component')
        else:
            pos += 1

            len_remainder = len_str - pos
            if len_remainder not in (3, 6):
                raise ValueError('Invalid microsecond component')

            time_comps[3] = int(tstr[pos:])
            if len_remainder == 3:
                time_comps[3] *= 1000

    return time_comps


def _parse_isoformat_time(tstr):
    # Format supported is HH[:MM[:SS[.fff[fff]]]][+HH:MM[:SS[.ffffff]]]
    len_str = len(tstr)
    if len_str < 2:
        raise ValueError('Isoformat time too short')

    # This is equivalent to re.search('[+-]', tstr), but faster
    tz_pos = (tstr.find('-') + 1 or tstr.find('+') + 1 or tstr.find('Z') + 1)
    timestr = tstr[:tz_pos - 1] if tz_pos > 0 else tstr

    time_comps = _parse_hh_mm_ss_ff(timestr)

    tzi = None
    if tstr[tz_pos - 1] == 'Z':
        tzi = UTC
    elif tz_pos > 0:
        tzstr = tstr[tz_pos:]

        # Valid time zone strings are:
        # HH:MM               len: 5
        # HH:MM:SS            len: 8
        # HH:MM:SS.ffffff     len: 15

        if len(tzstr) not in (5, 8, 15):
            raise ValueError('Malformed time zone string')

        tz_comps = _parse_hh_mm_ss_ff(tzstr)
        if all(x == 0 for x in tz_comps):
            tzi = UTC
        else:
            tzsign = -1 if tstr[tz_pos - 1] == '-' else 1

            td = datetime.timedelta(
                hours=tz_comps[0], minutes=tz_comps[1],
                seconds=tz_comps[2], microseconds=tz_comps[3])

            tzi = FixedOffsetTZ(tzsign * td, tzstr)

    time_comps.append(tzi)

    return time_comps


def datetime_from_isoformat(date_string):
    # Split this at the separator
    dstr = date_string[0:10]
    tstr = date_string[11:]

    try:
        date_components = _parse_isoformat_date(dstr)
    except ValueError:
        raise ValueError('Invalid isoformat string: {!r}'.format(date_string))

    if tstr:
        try:
            time_components = _parse_isoformat_time(tstr)
        except ValueError:
            raise ValueError('Invalid isoformat string: {!r}'.format(date_string))
    else:
        time_components = [0, 0, 0, 0, None]

    return datetime.datetime(*(date_components + time_components))


missing = object()


class cached_property(property):
    """From werkzeug source code:

    A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
    the value::

        class Foo(object):

            @cached_property
            def foo(self):
                # calculate something important here
                return 42

    The class has to have a `__dict__` in order for this property to
    work.
    """

    # implementation detail: A subclass of python's builtin property
    # decorator, we override __get__ to check for a cached value. If one
    # chooses to invoke __get__ by hand the property will still work as
    # expected because the lookup logic is replicated in __get__ for
    # manual invocation.

    def __init__(self, func, name=None, doc=None):
        super(cached_property, self).__init__()
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __set__(self, obj, value):
        obj.__dict__[self.__name__] = value

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, missing)
        if value is missing:
            value = self.func(obj)
            if value is missing:
                # don't cache when the function returns missing.
                return None
            obj.__dict__[self.__name__] = value
        return value
