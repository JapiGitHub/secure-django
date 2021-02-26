# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Module called when sitecustomize is automatically imported by python
"""
import imp
import os.path
import sys

from sqreen import start

LOADING = True

# Try to import other sitecustomize files in the path

current_directory = os.path.dirname(__file__)

# Remove ourselves from sys.path avoiding an import loop
if current_directory in sys.path:
    sys.path.remove(current_directory)

try:
    (file, pathname, description) = imp.find_module("sitecustomize", sys.path)
except ImportError:
    # There can no other sitecustomize
    pass
else:
    imp.load_module("sitecustomize", file, pathname, description)


start()
