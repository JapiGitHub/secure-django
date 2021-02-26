# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" Sqreen Python agent thread composition
"""
import atexit
import json
import os
import random
import sys
import threading
import time
import traceback
from copy import copy
from logging import getLogger
from threading import Event, Thread

from .__about__ import __version__
from ._vendors.sqreen_security_signal_sdk.sender import AuthenticationFailed
from ._vendors.urllib3 import PoolManager, ProxyManager
from ._vendors.urllib3.exceptions import HTTPError  # type: ignore
from ._vendors.urllib3.util import Timeout
from .actions import ActionStore
from .config import CONFIG
from .constants import CHANGELOG_URL, COMPATIBILITY_URL, STATUS_URL
from .deliverer import get_deliverer
from .ecosystem import init as init_ecosystem
from .exceptions import (
    InvalidApplicationName,
    UnsupportedFrameworkVersion,
    UnsupportedPythonVersion,
)
from .frameworks import debug
from .http_client import Urllib3Connection
from .instrumentation import Instrumentation
from .interface_manager import InterfaceManager
from .log import configure_root_logger
from .metrics import MetricsStore
from .reactive import Engine as Reactive
from .remote_command import RemoteCommand
from .remote_exception import RemoteException
from .runner import (
    CappedQueue,
    Runner,
    RunnerSettings,
    RunnerStop,
    process_initial_commands,
)
from .runtime_infos import (
    RuntimeInfos,
    get_parent_cmdline,
    get_process_cmdline,
)
from .session import InvalidSession, InvalidToken, Session
from .utils import (
    HAS_TYPING,
    configure_newrelics_ignore_exception,
    configure_raven_breadcrumbs,
    configure_sentry_ignore_errors,
)

if sys.version_info[0] < 3:
    import urlparse

    from ._vendors.concurrent.futures import ThreadPoolExecutor, TimeoutError
else:
    import urllib.parse as urlparse
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

if HAS_TYPING:
    from typing import Optional, Sequence

RUNNER_THREAD = None
RUNNER_THREAD_RESTARTING = False
RUNNER_LOCK = threading.RLock()

LOGGER = getLogger(__name__)


def uwsgi_version_info():
    """Return uWSGI version tuple if run in uWSGI, None otherwise."""
    # Import must be delayed inside the function, because the uwsgi module is
    # not known by sqreen-start.
    try:
        import uwsgi  # type: ignore
    except ImportError:
        return None
    else:
        return uwsgi.version_info


def should_start_runner_thread():
    """This function contains the logic used to check if the thread
    should be restarted. Beware, this function *must not* call any hooks.
    """
    global RUNNER_THREAD

    return getattr(RUNNER_THREAD, "pid", None) != os.getpid() and not \
        getattr(getattr(RUNNER_THREAD, "runner", None), "stop", False)


def before_hook_point():
    global RUNNER_THREAD
    global RUNNER_THREAD_RESTARTING

    # /!\ The order of execution in this function must not change
    # without a careful review. /!\
    if should_start_runner_thread():
        # It is cheap to first call should_start_runner_thread instead
        # of just locking everytime.
        with RUNNER_LOCK:
            # If we are in a recursive call, do nothing
            if RUNNER_THREAD_RESTARTING is True:
                LOGGER.debug("The runner thread is already restarting")
                return
            # If a concurrent thread has already started the thread, do nothing
            if not should_start_runner_thread():
                LOGGER.info("The runner thread has already been started")
                return
            # Else, restart the thread
            try:
                RUNNER_THREAD_RESTARTING = True
                RUNNER_THREAD = RUNNER_THREAD.replace()
                RUNNER_THREAD.start()

                LOGGER.info(
                    "Successfully started runner thread for pid: %d",
                    RUNNER_THREAD.pid
                )
            finally:
                RUNNER_THREAD_RESTARTING = False


BLACKLISTED_PARENT_COMMANDS = (
    "ipython",
    "celery worker",
    "rq worker",
    "manage.py shell",
    "pshell",
)
BLACKLISTED_COMMANDS = BLACKLISTED_PARENT_COMMANDS + ("newrelic-admin",)


def get_app_name():
    """ Get the current application name. Return a string if the name is valid.
    Raise InvalidApplicationName otherwise.
    """
    config_app_name = CONFIG["APP_NAME"]
    if config_app_name is not None:
        app_name = config_app_name
    elif CONFIG["SERVERLESS_DETECTION"] and "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
        app_name = os.environ["AWS_LAMBDA_FUNCTION_NAME"]
    else:
        app_name = "python-application"

    try:
        if isinstance(app_name, bytes):
            app_name = app_name.decode("utf-8")
    except UnicodeDecodeError:
        raise InvalidApplicationName

    # Check the app name is not empty and does not contain
    # any invalid characters (ASCII control chars lower than 0x20)
    if not app_name or any([ord(c) < 0x20 for c in app_name]):
        raise InvalidApplicationName

    return app_name


def get_session(url, token, app_name=None, proxy_url=None, use_legacy_url=False, ingestion_url=None):
    """ Create a connection with the endpoint URL and a session. Returns only
    the session.
    """
    LOGGER.warning(
        "Connection to %s%s%s",
        "legacy " if use_legacy_url else "",
        url,
        " using proxy %s" % proxy_url if proxy_url else "",
    )
    con = Urllib3Connection(url, proxy_url=proxy_url, use_legacy_url=use_legacy_url)
    session = Session(con, token, app_name, ingestion_url=ingestion_url)
    return session


def get_proxy_url():
    """ Returns the HTTP proxy url or None if not set.
    """
    legacy_name = CONFIG["PROXY_URL"]
    new_name = CONFIG["HTTP_PROXY"]
    if legacy_name and new_name:
        LOGGER.warning("Both proxy_url and http_proxy are set, using http_proxy.")
    return new_name or legacy_name


def post_app_sqreen_exception(data):
    # type: (RemoteException) -> None
    """Post a Sqreen exception happening at application level.
    This function does not need a session. It always uses the legacy backend URL
    until all customers are migrated.

    This function is used to report instrumentation errors. It should never
    fail.
    """
    token = CONFIG["TOKEN"]
    if not token:
        return

    try:
        app_name = get_app_name()
        session = get_session(
            CONFIG["LEGACY_URL"], token, app_name, proxy_url=get_proxy_url(),
            use_legacy_url=True
        )
        session.post_app_sqreen_exception(data)
    except Exception:
        pass


def start():
    # type: () -> None
    """ Start the background thread and start protection
    """
    # Configure logging
    configure_root_logger(CONFIG["LOG_LEVEL"], CONFIG["LOG_LOCATION"])

    # Check if the agent is not disabled
    if CONFIG["DISABLE"]:
        LOGGER.debug("Sqreen agent is disabled.")
        return

    # Retrieve the command used to launch the process
    command = get_process_cmdline()

    # Retrieve the parent command
    parent_command = get_parent_cmdline()

    # Check if we shouldn't launch ourselves
    for blacklisted_command in BLACKLISTED_COMMANDS:
        if blacklisted_command in command:
            LOGGER.debug(
                "Sqreen agent is disabled when running %s.",
                blacklisted_command,
            )
            return
    for blacklisted_parent_command in BLACKLISTED_PARENT_COMMANDS:
        if blacklisted_parent_command in parent_command:
            LOGGER.debug(
                "Sqreen agent is disabled when running %s.",
                blacklisted_parent_command,
            )
            return
    if hasattr(sys, "argv") and len(sys.argv) >= 2 and sys.argv[1] == "test":
        LOGGER.debug("Sqreen agent is disabled when running tests.")
        return

    try:
        runtime_infos = RuntimeInfos().all()
    except UnsupportedFrameworkVersion as exception:
        msg = (
            "%s version %s is not supported in this agent version.\n"
            "Sqreen agent is disabled, you're not protected.\n"
            "Documentation can be found at %s.\n"
            "Changelog can be found at %s."
        )
        LOGGER.critical(
            msg,
            exception.framework.title(),
            exception.version,
            COMPATIBILITY_URL,
            CHANGELOG_URL,
        )
        # Alter os.environ?
        return
    except UnsupportedPythonVersion as exception:
        msg = (
            "Python version %s is not supported in this agent version.\n"
            "Sqreen agent is disabled, you're not protected.\n"
            "Documentation can be found at %s.\n"
            "Changelog can be found at %s."
        )
        LOGGER.critical(
            msg, exception.python_version, COMPATIBILITY_URL, CHANGELOG_URL
        )
        return
    except Exception:
        msg = (
            "Runtime information about the system could not be retrieved.\n"
            "Sqreen agent is disabled, you're not protected.\n"
            "Documentation can be found at %s.\n"
        )
        LOGGER.critical(msg, COMPATIBILITY_URL)
        post_app_sqreen_exception(RemoteException.from_exc_info())
        return

    # Configure raven breadcrumbs and sentry SDK at start
    configure_raven_breadcrumbs()
    configure_sentry_ignore_errors()

    # Ignore Sqreen Exception from APM NewRelics
    configure_newrelics_ignore_exception()

    global RUNNER_THREAD

    # Check for double instrumentation
    if RUNNER_THREAD is None:
        try:
            RUNNER_THREAD = RunnerThread(runtime_infos)
            RUNNER_THREAD.start()

            timeout = CONFIG["INSTRUMENTATION_TIMEOUT"]
            if RUNNER_THREAD.serverless:
                timeout = min(timeout, CONFIG["SERVERLESS_INSTRUMENTATION_TIMEOUT"])

            done = RUNNER_THREAD.unblock_main_thread.wait(timeout)
            if done is not True:
                LOGGER.critical(
                    "Sqreen could not instrument your application in less than %ds.\n"
                    "Please check your account is not expired and your application has network connectivity.\n"
                    "You can also check Sqreen status on %s.",
                    timeout, STATUS_URL)

        except Exception:
            LOGGER.critical(
                "Sqreen thread has failed to start, you're not protected",
                exc_info=True,
            )
            return


def sqreen_compatible_backends(base_urls, proxy_url=None):
    # type: (Sequence[str], Optional[str]) -> bool
    """ Detect Sqreen backend reachability.
    """
    LOGGER.debug("Detecting reachability to: %s", ", ".join(base_urls))
    timeout_policy = Timeout(total=30)
    http = PoolManager(timeout=timeout_policy) if proxy_url is None \
        else ProxyManager(proxy_url=proxy_url, timeout=timeout_policy)

    def request(base_url):
        url = urlparse.urljoin(base_url, "/ping")
        r = http.urlopen("GET", url)
        return r.status == 200

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            return all(executor.map(request, base_urls, timeout=30))
    except TimeoutError:
        return False
    except Exception:
        LOGGER.debug("Couldn't detect domains", exc_info=True)
        return False


def get_initial_features(config_features, login_features):
    LOGGER.debug("Login features: %s", login_features)

    final_features = copy(login_features)

    if config_features:
        parsed_config_features = {}
        try:
            parsed_config_features = json.loads(config_features)
        except (ValueError, TypeError):
            LOGGER.warning(
                "Invalid config initial features %s",
                config_features,
                exc_info=True,
            )

        if parsed_config_features and isinstance(parsed_config_features, dict):
            msg = "Override login initial features with %s"
            LOGGER.warning(msg, parsed_config_features)

            final_features.update(parsed_config_features)

            LOGGER.warning("Final features %s", final_features)

    return final_features


def get_runner(
    config,
    login_result,
    session,
    queue,
    runtime_infos,
    observations_queue,
    instrumentation,
    settings,
    interface_manager,
    reactive,
):
    initial_features = get_initial_features(
        config["INITIAL_FEATURES"], login_result.get("features", {})
    )

    # Get a signal client if the feature is enabled
    session.use_signals = initial_features.get("use_signals", False)

    # Get the right deliverer according to initial features
    deliverer = get_deliverer(
        initial_features.get("batch_size", 0),
        initial_features.get("max_staleness", 0),
        session,
    )
    remote_command = RemoteCommand.with_production_commands()
    action_store = ActionStore()
    metrics_store = MetricsStore()
    metrics_store.register_production_aggregators()

    # Setup the runner
    runner = Runner(
        queue,
        observations_queue,
        session,
        deliverer,
        remote_command,
        runtime_infos,
        instrumentation,
        action_store,
        metrics_store,
        settings,
        initial_features,
        interface_manager=interface_manager,
        reactive=reactive,
    )
    return runner


class RunnerThread(Thread):
    """ Class responsible for starting the runner and monitor it
    """

    name = "SqreenRunnerThread"

    def __init__(self, runtime_infos, queue=None, observations_queue=None,
                 instrumentation=None, settings=None, interface_manager=None,
                 reactive=None):
        super(RunnerThread, self).__init__()
        self.daemon = True
        self.queue = queue or CappedQueue(CONFIG["MAX_QUEUE_LENGTH"])
        self.observations_queue = observations_queue or CappedQueue(CONFIG["MAX_OBS_QUEUE_LENGTH"], name="observations_queue")
        self.unblock_main_thread = Event()
        self.runtime_infos = runtime_infos
        self.instrumentation = instrumentation or Instrumentation(before_hook_point)
        self.settings = settings or RunnerSettings()
        if CONFIG["BETA_STATIC_INSTRUMENTATION"]:
            interface_manager = interface_manager or InterfaceManager()
        self.interface_manager = interface_manager
        self.reactive = reactive or Reactive()
        self.runner = None
        self.started = False
        self.pid = None

    @property
    def serverless(self):
        if not CONFIG["SERVERLESS_DETECTION"]:
            return False
        aws_lambda = self.runtime_infos.get("various_infos", {}).get("aws_lambda", {})
        return aws_lambda.get("sqreen_extension", False)

    @property
    def stacktrace(self):
        """Get the runner thread stack trace if it exists.
        """
        frame = sys._current_frames().get(self.ident, None)
        if frame is not None:
            return traceback.extract_stack(frame)

    def run(self):
        """ Launch the runner
        """
        self.started = True
        LOGGER.debug("Starting Sqreen %s", __version__)
        while True:
            session = None
            self.runner = None

            try:
                token = CONFIG["TOKEN"]
                if not token:
                    msg = (
                        "Sorry but we couldn't find your Sqreen token.\n"
                        "Your application is NOT currently protected by Sqreen.\n"
                        "\n"
                        "Have you filled your sqreen.ini?"
                    )
                    LOGGER.critical(msg)
                    self.unblock_main_thread.set()
                    return

                try:
                    app_name = get_app_name()
                except InvalidApplicationName:
                    msg = (
                        "Sorry but your application name seems invalid.\n"
                        "Your application is NOT currently protected by Sqreen.\n"
                        "\n"
                        "Please visit the following link: https://docs.sqreen.com/faq/org-token-migration/#application-name-limitations"
                    )
                    LOGGER.critical(msg)
                    self.unblock_main_thread.set()
                    return

                LOGGER.warning("Using token %r and application name %r", token, app_name)

                if not self.serverless:
                    if not CONFIG["NO_SNIFF_DOMAINS"]:
                        # Detect if the configured URLs are reachable.
                        use_legacy_url = not sqreen_compatible_backends(
                            [CONFIG["URL"], CONFIG["INGESTION_URL"]], proxy_url=get_proxy_url())
                    else:
                        # Force use of the configured URLs.
                        use_legacy_url = False

                    # Initiate HTTP connection to the backend and the session, fallback to the legacy URL
                    # if the new URLs are not available.
                    if use_legacy_url:
                        LOGGER.info("Using legacy URLs for backend communication")
                        session_url = ingestion_url = CONFIG["LEGACY_URL"]
                    else:
                        LOGGER.info("Using new URLs for backend communication")
                        session_url, ingestion_url = CONFIG["URL"], CONFIG["INGESTION_URL"]
                    proxy_url = get_proxy_url()
                else:
                    LOGGER.info("Using serverless extension for backend communication")
                    session_url = ingestion_url = CONFIG["SERVERLESS_EXTENSION_URL"]
                    proxy_url = None
                    use_legacy_url = False

                session = get_session(
                    session_url, token, app_name, proxy_url=proxy_url, use_legacy_url=use_legacy_url,
                    ingestion_url=ingestion_url
                )

                runtime_infos = dict(self.runtime_infos)
                runtime_infos["various_infos"] = {
                    k: v
                    for k, v in runtime_infos.get("various_infos", {}).items()
                    if k != "dependencies"
                }
                try:
                    login_result = session.login(runtime_infos)
                except InvalidToken:
                    msg = (
                        "Sorry but your Sqreen token appears to be invalid.\n"
                        "Your application is NOT currently protected by Sqreen.\n"
                        "\n"
                        "Please check the token against the interface."
                    )
                    LOGGER.critical(msg)
                    self.unblock_main_thread.set()
                    return
                except HTTPError:
                    msg = (
                        "Sorry but Sqreen's backend appears to be unavailable.\n"
                        "Your application is NOT currently protected by Sqreen.\n"
                        "\n"
                        "Please check http://sqreen.status.io for outage.\n"
                        "\n"
                        "Otherwise, back.sqreen.io may be blocked by your server's network.\n"
                        "If necessary, you may tell Sqreen to connect over a proxy.\n"
                        "Please visit https://docs.sqreen.com/python/configuration/ for more details."
                    )
                    LOGGER.critical(msg)
                    self.unblock_main_thread.set()
                    return

                LOGGER.info("Login success")

                if self.interface_manager is not None:
                    LOGGER.debug("Initializing ecosystem")
                    init_ecosystem(self.interface_manager)

                self.runner = get_runner(
                    CONFIG,
                    login_result,
                    session,
                    self.queue,
                    self.runtime_infos,
                    self.observations_queue,
                    self.instrumentation,
                    self.settings,
                    self.interface_manager,
                    self.reactive,
                )

                # Process the initial commands
                process_initial_commands(login_result, self.runner)

                self.unblock_main_thread.set()

                # No background thread for the serverless mode
                if self.serverless:
                    return

                while True:
                    try:
                        self.runner.run()
                    except HTTPError:
                        LOGGER.debug("An HTTP error occurred, restarting runner", exc_info=True)
                        try:
                            session.post_sqreen_exception(
                                RemoteException.from_exc_info()
                            )
                        except HTTPError:
                            pass
                        self._random_sleep()
                    else:
                        # If the runner exits normally, return.
                        return
            except (AuthenticationFailed, InvalidSession):
                LOGGER.debug("Relaunching the session because it was dropped by the backend.")
                self._random_sleep()
            except Exception as exc:
                LOGGER.debug("An unexpected exception occurred", exc_info=True)

                callback_payload = getattr(exc, "callback_payload", None)
                exception_payload = getattr(exc, "exception_payload", None)
                request_payload = getattr(exc, "request_payload", None)
                remote_exception = RemoteException.from_exc_info(
                    callback_payload=callback_payload,
                    exception_payload=exception_payload,
                    request_payload=request_payload,
                )

                if session is not None and session.is_connected():
                    try:
                        session.post_sqreen_exception(remote_exception)
                        session.logout()
                    except HTTPError:
                        LOGGER.debug("An HTTP error occurred while logout", exc_info=True)
                    except Exception:
                        LOGGER.debug("Exception while logout", exc_info=True)
                        return
                else:
                    post_app_sqreen_exception(remote_exception)

                try:
                    self.instrumentation.settings.remove_callbacks()
                except Exception:
                    # We did not managed to remove instrumentation, state is unclear:
                    # terminate thread
                    LOGGER.debug("Exception while trying to clean-up", exc_info=True)
                    return

                self._random_sleep()

    def quick_exit(self):
        """Check for early exit."""
        if os.environ.get("SQREEN_SKIP_LOGOUT", False):
            return True
        # uWSGI 2.0.15 may segfault upon exiting.
        # See https://github.com/unbit/uwsgi/issues/1651.
        uwsgi_vers = uwsgi_version_info()
        if uwsgi_vers and uwsgi_vers >= (2, 0, 15):
            return True
        return self.settings.get_debug_flag() or debug.detect_debug_mode()

    def start(self):
        """Start the runner thread."""
        self.pid = os.getpid()
        atexit.register(self.graceful_stop)
        return super(RunnerThread, self).start()

    def graceful_stop(self, force_quick_exit=False):
        """Gracefully stop the runner thread and wait for its termination."""
        self.queue.put(RunnerStop)

        if force_quick_exit or self.quick_exit():
            LOGGER.warning("Quick exit, don't logout")
            return

        GRACEFUL_FAIL_MSG = "Sqreen thread didn't exit after %s seconds"
        try:
            self.join(CONFIG["GRACEFUL_TIMEOUT"])
        except RuntimeError:
            logger = getLogger(__name__)
            logger.warning(GRACEFUL_FAIL_MSG, CONFIG["GRACEFUL_TIMEOUT"])
        else:
            if self.isAlive():
                logger = getLogger(__name__)
                logger.warning(GRACEFUL_FAIL_MSG, CONFIG["GRACEFUL_TIMEOUT"])

    def replace(self, **kwargs):
        """Create a new runner thread instance."""
        nkwargs = dict(
            queue=self.queue,
            observations_queue=self.observations_queue,
            instrumentation=self.instrumentation,
            settings=self.settings,
            interface_manager=self.interface_manager,
            reactive=self.reactive,
        )
        nkwargs.update(kwargs)
        return self.__class__(RuntimeInfos().all(), **nkwargs)

    @classmethod
    def _random_sleep(cls, max_delay=10.0):
        """Sleep for a random duration before trying again."""
        delay = random.uniform(0, max_delay)
        LOGGER.info("Sleeping %0.2fs before retry", delay)
        time.sleep(delay)
