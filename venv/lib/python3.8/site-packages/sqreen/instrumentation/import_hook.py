# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Import hook related helpers
"""
import logging
import sys
import threading

if sys.version_info >= (3, 4):
    from importlib.util import find_spec
    PY3_IMPORT_HOOK = True
else:
    find_spec = None
    PY3_IMPORT_HOOK = False

LOGGER = logging.getLogger(__name__)


def get_hook_parent(module, hook_class):
    """ From a module and a class, retrieve the right class
    and returns both the hook parent and the full hook path
    """
    if hook_class:
        if "." in hook_class:
            raise NotImplementedError()
        else:
            return getattr(module, hook_class, None)
    else:
        return module


def get_module_parent(module_name):
    """ Return the parent module name

    >>> get_module_parent('django.conf')
    'django'
    >>> get_module_parent('django')
    'django'
    """
    splitted = module_name.split(".")
    if len(splitted) == 1:
        return module_name
    else:
        return ".".join(splitted[:-1])


def get_original(module, module_class_name, module_object_name):
    """ Return the object in module at path module_class_name / module_object_name

    For example: 'itertools:None:count' would target the function named count
        in the itertools module.
        And 'django.core.handlers.wsgi:WSGIHandler:__call__' would target the
        method '__call__' of the class 'WSGIHandler' in the module
        'django.core.handlers.wsgi'.
    """
    # Get module class
    module_class = get_hook_parent(module, module_class_name)

    if module_class is None:
        LOGGER.info("Module %r has no attribute %r", module, module_class_name)
        return None

    # Get module object
    module_object = get_hook_parent(module_class, module_object_name)

    if module_object is None:
        LOGGER.info(
            "Module class %r::%r (%r) has no attribute %r",
            module,
            module_class_name,
            module_class,
            module_object_name,
        )
        return None

    return module_object


def update_original(module, patched, module_class_name, module_object_name):
    """ Update the object at the path module_class_name + module_object in the
    module with patched.
    The paths are the same that get_original.
    """
    module_class = get_hook_parent(module, module_class_name)
    setattr(module_class, module_object_name, patched)


class ExistingPatchOnSameObject(Exception):
    """ Raise in case a patcher is already present for the same object
    """

    pass


class ModuleFinder(object):
    """ Custom import hook for Python 2/3 that import a module and hook on several
    hook points of this module
    """

    def __init__(self):
        self.patchers = {}
        self.loading = {}
        # The ModuleFinder is used across all threads so we must lock the
        # patching operation to prevent race conditions. In fact, a thread can be
        # loading a module while a second tries to patch it. It leads to random errors
        # such as "module has no attribute".
        # The lock is recursive because the find_module method calls itself.
        self.lock = threading.RLock()

    def register_patcher(
        self, module_name, module_class, module_object, patcher
    ):
        """ Register a patcher for a specific path, a path is composed of
        module_name, module_class and module_object.
        For example: 'itertools:None:count' would target the function named count
        in the itertools module.
        And 'django.core.handlers.wsgi:WSGIHandler:__call__' would target the
        method '__call__' of the class 'WSGIHandler' in the module
        'django.core.handlers.wsgi'.

        There could be only one patcher per path, if a patcher is already
        registered for a path, a ExistingPatchOnSameObject exception will be
        raised.
        """
        path = "%s:%s:%s" % (module_name, module_class, module_object)
        LOGGER.debug("Adding patcher on %s", path)
        patchers = self.patchers.setdefault(module_name, {}).setdefault(
            module_class, {}
        )

        if module_object in patchers:
            raise ExistingPatchOnSameObject("Patcher already here")

        patchers[module_object] = {"patcher": patcher, "patched": False}

    def inject(self):
        """ Inject the global import hook in sys.meta_path if it's not already
        present
        """
        if sys.meta_path[0] is not self:
            sys.meta_path.insert(0, self)

    def apply_patchers(self):
        """ Try to apply not already applied patchers on modules already present
        in sys.modules as they would not be applied otherwise.
        """
        # Block the patching operation if there are still modules loading.
        with self.lock:
            for module_name, _ in self.patchers.items():

                if module_name in sys.modules:
                    msg = "Module %s was already imported, hooking now"
                    LOGGER.warning(msg, module_name)

                    self.patch_module(module_name, sys.modules[module_name])

    def patch_module(self, fullname, module):
        """ For a module named fullname, apply all patchers defined for it
        """
        for module_class, module_objects in self.patchers.get(
            fullname, {}
        ).items():
            for module_object, patcher in module_objects.items():
                if patcher["patched"] is False:
                    self._patch(module, module_class, module_object, patcher)
                else:
                    path = "%s:%s:%s" % (fullname, module_class, module_object)
                    LOGGER.debug(
                        "Patcher %r already applied for %s",
                        patcher["patcher"],
                        path,
                    )

        return module

    def _patch(self, module, module_class, module_object, patcher):
        """ Apply a single patcher on a single path
        """
        # Retrieve the original method
        original = get_original(module, module_class, module_object)
        if original is not None:
            # Patch it
            patched = patcher["patcher"](original)
            # And update back the module
            update_original(module, patched, module_class, module_object)
        # Mark as already patched
        patcher["patched"] = True

    def find_module(self, fullname, path=None):
        """ Import hook main API, called when the application try to import
        every module not already in sys.modules.
        """
        # Early exit
        if fullname not in self.patchers:
            return

        # Lock because we are currently loading a module.
        with self.lock:
            is_loading = fullname in self.loading
            # Avoid recursion as we import the module in a way that recheck every
            # import hook
            if is_loading:
                LOGGER.debug("Looking for already loading module %s", fullname)
                return

            self.loading[fullname] = True
            try:

                # In python 2, call back the whole import mechanism but ignoring
                # ourself
                if PY3_IMPORT_HOOK is False:
                    __import__(fullname)

                    modules_keys = sys.modules
                    if (
                        fullname in modules_keys
                        or get_module_parent(fullname) in modules_keys
                    ):
                        return self
                # In python 3, call loader
                else:
                    spec = find_spec(fullname, path)
                    if spec is not None and spec.loader is not None:
                        return ModuleLoader(spec.loader, self)

                LOGGER.debug("Module %s was not loaded", fullname)

            finally:
                del self.loading[fullname]

    def load_module(self, fullname):
        """ Load the module either from sys.modules or from its parent module.
        Used only in Python 2.
        """
        # Block the patching while we are loading a module.
        with self.lock:
            if fullname in sys.modules:
                module = sys.modules[fullname]
            else:
                parent_module_name = get_module_parent(fullname)
                if parent_module_name in sys.modules:
                    parent_module = sys.modules[parent_module_name]

                    module = getattr(parent_module, fullname.split(".")[-1])

            return self.patch_module(fullname, module)


class ModuleLoader(object):
    """ A module loader for Python 3
    """

    def __init__(self, loader, finder):
        self.loader = loader
        self.finder = finder

    def load_module(self, fullname):
        """ Import hook in python 3 call for loading a module
        """
        # Block the ModuleFinder from patching while we are loading a module.
        with self.finder.lock:
            module = self.loader.load_module(fullname)
            return self.finder.patch_module(fullname, module)
