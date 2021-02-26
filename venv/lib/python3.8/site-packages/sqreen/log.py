# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Logging module helpers
"""
import logging
import os
import stat

ROOT_LOGGER_NAME = "sqreen"
LOG_FORMAT = (
    "[%(levelname)s][%(asctime)s #%(process)d.%(threadName)s]"
    " %(name)s:%(lineno)s \t%(message)s"
)


def configure_root_logger(log_level=logging.CRITICAL, log_location=None, root=ROOT_LOGGER_NAME):
    """ Configure the sqreen root logger. Set following settings:

    - log_level

    Ensure that the sqreen root logger don't propagate messages logs
    to the python root logger.
    Configure two handlers, one stream handler on stderr for errors
    and one file handler if log_location is set for configured level
    """
    logger = logging.getLogger(root)

    # Don't propagate messages to upper loggers
    logger.propagate = False
    logger.handlers = []

    formatter = logging.Formatter(LOG_FORMAT)

    # Configure the stderr handler configured on CRITICAL level
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    try:
        logger.setLevel(log_level)
    except ValueError:
        logger.error("Unknown log_level %r, default log level is CRITICAL", log_level)
        logger.setLevel(logging.CRITICAL)

    if log_location is not None:
        try:
            filehandler = logging.FileHandler(log_location)
            os.chmod(log_location, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
            filehandler.setFormatter(formatter)
            logger.addHandler(filehandler)
        except (OSError, IOError):
            msg = "Couldn't use %s as sqreen log location, fallback to stderr."
            logger.error(msg, log_location, exc_info=True)
        else:
            stderr_handler.setLevel(logging.CRITICAL)

    return logger
