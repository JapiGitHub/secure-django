# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Script modifying the env to run our sitecustomize script before everyone else
"""
import argparse
import os
from os.path import dirname

from ..constants import INSTALLATION_URL


def where_sitecustomize():
    """ Returns the path of the sitecustomize package
    """
    current_file = os.path.split(__file__)[0]
    path = os.path.join(dirname(current_file), "sitecustomize")
    return path


def create_parser(parser_cls=argparse.ArgumentParser):
    parser = parser_cls(
        description=(
            "Launch a web application protected by the Sqreen agent.\n"
            "You can check {} for more information.".format(INSTALLATION_URL)
        )
    )
    parser.add_argument("command", help="command to run the application")
    parser.add_argument("arguments", nargs=argparse.REMAINDER, metavar="...")
    return parser


def prepend_pythonpath(pythonpath, environ):
    patched_environ = dict(environ)
    current_pythonpath = environ.get("PYTHONPATH")
    if current_pythonpath is None:
        current_pythonpath = pythonpath
    else:
        current_pythonpath = os.pathsep.join([pythonpath, current_pythonpath])
    patched_environ["PYTHONPATH"] = current_pythonpath
    return patched_environ


def protect(args=None):
    """ Call the passed binary passed in argument with the right PYTHONPATH
    """
    parser = create_parser()
    args = parser.parse_args(args)
    environ = prepend_pythonpath(where_sitecustomize(), os.environ)
    os.execvpe(args.command, [args.command] + args.arguments, environ)
