# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
import os
import sys


def detect_debug_mode():
    """ Detect if any supported and already loaded framework is in debug mode.

    Not all frameworks support accessing this information globally. In this
    case, the "is_debug" method is exposed on the request wrapper.
    """
    modes = []

    # Django
    django_conf = sys.modules.get("django.conf", None)
    if django_conf is not None and hasattr(django_conf, "settings"):
        modes.append(getattr(django_conf.settings, "DEBUG", False))

    # Pyramid
    modes.append(bool(os.environ.get("PYTHON_RELOADER_SHOULD_RUN", False)))

    # asyncio
    asyncio_module = sys.modules.get("asyncio", None)
    if asyncio_module is not None:
        try:
            modes.append(asyncio_module.get_event_loop().get_debug())
        except Exception:
            pass

    return any(modes)
