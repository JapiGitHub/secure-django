# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Authentication SDK functions
"""
from ..utils import HAS_TYPING

if HAS_TYPING:
    from typing import Mapping, Optional, Union

    UserIdentifier = Union[str, int]
    UserDict = Mapping[str, UserIdentifier]


def _identify(user_identifiers, traits=None):
    pass


def _auth_track(success, **user_identifiers):
    pass


def _signup_track(**user_identifiers):
    pass


def identify(user_identifiers, traits=None):
    # type: (UserDict, Optional[Mapping]) -> None
    """ Associate the current request with the account identified by
    the identifier.

    Example:

    >>> identify({"user_id": 42, "email": "foobar@example.com"})
    """
    _identify(user_identifiers, traits)


def auth_track(success, **user_identifiers):
    # type: (bool, **UserIdentifier) -> None
    """ Register a successfull or failed authentication attempt (based on
    success boolean) for an user identified by the keyword-arguments.
    For example:

    Register a successfull authentication attempt for user with email
    "foobar@example.com":

    >>> auth_track(True, email="foobar@example.com")

    Register a failed authentication attempt for user with id 42:

    >>> auth_track(False, user_id=42)
    """
    if success:
        identify(user_identifiers)
    _auth_track(success, **user_identifiers)


def signup_track(**user_identifiers):
    # type: (**UserIdentifier) -> None
    """ Register a new account signup identified by the keyword-arguments.
    For example:

    Register a new account signup for user identifed by email "foobar@example.com" or
    bu user id 42:

    >>> auth_track(email="foobar@example.com", user_id=42)
    """
    identify(user_identifiers)
    _signup_track(**user_identifiers)
