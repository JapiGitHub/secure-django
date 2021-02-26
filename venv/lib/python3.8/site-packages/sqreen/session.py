# -*- coding: utf-8 -*-
# Copyright (c) 2016 - 2020 Sqreen. All rights reserved.
# Please refer to our terms for more information:
#
#     https://www.sqreen.io/terms.html
#
""" High-level interaction with sqreen API
"""
import logging

from ._vendors.sqreen_security_signal_sdk import Signal, SignalType, sender
from ._vendors.urllib3.exceptions import (  # type: ignore
    HTTPError,
    MaxRetryError,
)
from .config import CONFIG
from .events import Attack, RequestRecord
from .exceptions import SqreenException
from .http_client import InvalidStatusCodeResponse, StatusFailedResponse
from .remote_exception import RemoteException
from .runtime_infos import get_agent_type
from .utils import HAS_TYPING, now

if HAS_TYPING:
    from typing import Mapping, MutableMapping, Optional, Sequence, Union

    from ._vendors.sqreen_security_signal_sdk.compat_model import AnySignal


LOGGER = logging.getLogger(__name__)


class InvalidToken(Exception):
    """ Exception raise when a login fails because of the token value
    """


class InvalidSession(Exception):
    """ Exception raise when the session is not valid anymore.
    """


class LegacyEvents:
    """ Legacy events submission strategy posts agent events
    to the legacy backend.
    """

    def __init__(self, session):
        self.session = session

    def post_signal(self, event):
        raise NotImplementedError("Cannot send signals to the legacy backend.")

    def post_attack(self, attack):
        # type: (Attack) -> Optional[Mapping]
        return self.session._post(
            "v0/attack", attack.to_dict(),
            retries=self.session.connection.RETRY_LONG
        )

    def post_sqreen_exception(self, exception, last_resort=False):
        # type: (RemoteException, bool) -> Optional[Mapping]
        return self.session._post(
            "v0/sqreen_exception", exception.to_dict(),
            retries=self.session.connection.RETRY_LONG, last_resort=last_resort
        )

    def post_metrics(self, metrics):
        # type: (Sequence[Mapping]) -> Optional[Mapping]
        # Don't send empty metrics payload
        if not metrics:
            return None

        data = {"metrics": [
            {k: v for k, v in metric.items() if k in ("name", "observation", "start", "finish")}
            for metric in metrics
        ]}

        return self.session._post(
            "v0/metrics", data, retries=self.session.connection.RETRY_ONCE
        )

    def post_request_record(self, request_record):
        # type: (RequestRecord) -> Optional[Mapping]
        return self.session._post(
            "v0/request_record",
            request_record.to_dict(),
            retries=self.session.connection.RETRY_LONG
        )

    @staticmethod
    def _format_event(event):
        # type: (Union[RemoteException, Attack, RequestRecord]) -> Mapping
        """ Format an event for the batch depending of its type
        """
        if isinstance(event, RemoteException):
            formatted = event.to_dict()
            formatted["event_type"] = "sqreen_exception"
        elif isinstance(event, Attack):
            formatted = event.to_dict()
            formatted["event_type"] = "attack"
        elif isinstance(event, RequestRecord):
            formatted = event.to_dict()
            formatted["event_type"] = "request_record"
        else:
            raise NotImplementedError(
                "Unknown event type {}".format(type(event))
            )
        return formatted

    def post_batch(self, batch, send_resiliently=True):
        # type: (Sequence[Union[RemoteException, Attack, RequestRecord]], bool) -> Optional[Mapping]

        if send_resiliently:
            retry_policy = self.session.connection.RETRY_LONG
        else:
            retry_policy = self.session.connection.RETRY_ONCE

        return self.session._post(
            "v0/batch", {
                "batch": [self._format_event(event) for event in batch]
            }, retries=retry_policy
        )

    def get_metrics(self, at=None):
        return []


class IngestionEvents:

    def __init__(self, sender):
        self.sender = sender
        self._sent = 0
        self._dropped = 0

    def post_signal(self, signal):
        try:
            self.sender.send_signal(signal)
        except (MaxRetryError, HTTPError) as exc:
            LOGGER.error("Couldn't send signal due to exception %s", type(exc).__name__)
            self._dropped += 1
        else:
            self._sent += 1

    def post_attack(self, attack):
        # type: (Attack) -> None
        raise NotImplementedError("Attack signal not supported outside a trace.")

    def post_sqreen_exception(self, exception, last_resort=False):
        # type: (RemoteException, bool) -> None
        try:
            self.sender.send_signal(exception.to_signal())
        except (MaxRetryError, HTTPError) as exc:
            LOGGER.error("Couldn't send remote exception due to exception %s", type(exc).__name__)
            self._dropped += 1
        else:
            self._sent += 1

    def post_metrics(self, metrics):
        # type: (Sequence[Mapping]) -> None
        batch = []
        for metric in metrics:
            payload = {
                "capture_interval_s": metric["period"],
                "date_started": metric["start"],
                "date_ended": metric["finish"],
            }
            if metric["kind"] == "Binning":
                payload_schema = "metric_binning/2020-01-01T00:00:00.000Z"
                o = metric["observation"]
                payload.update({
                    "unit": o["u"],
                    "base": o["b"],
                    "bins": o["v"],
                    "max": o["v"].pop("max"),
                })
            else:
                payload_schema = "metric/2020-01-01T00:00:00.000Z"
                payload.update({
                    "kind": metric["kind"].lower(),
                    "values": [{"key": str(k), "value": v}
                               for k, v in metric["observation"].items()],
                })
            batch.append(Signal(
                type=SignalType.METRIC,
                signal_name="sq.agent.metric.{}".format(metric["name"]),
                payload=payload,
                payload_schema=payload_schema,
                source="sqreen:agent:{}".format(get_agent_type()),
                time=metric["start"],
            ))
        self.post_batch(batch)

    def post_request_record(self, request_record):
        # type: (RequestRecord) -> None
        try:
            self.sender.send_trace(request_record.to_trace())
        except (MaxRetryError, HTTPError) as exc:
            LOGGER.error("Couldn't send request record due to exception %s", type(exc).__name__)
            self._dropped += 1
        else:
            self._sent += 1

    @staticmethod
    def _format_event(event):
        # type: (Union[RemoteException, Attack, RequestRecord, Signal]) -> AnySignal
        if isinstance(event, RemoteException):
            return event.to_signal()
        elif isinstance(event, RequestRecord):
            return event.to_trace()
        elif isinstance(event, dict):
            return event
        raise NotImplementedError(
            "Unknown event type {}".format(type(event))
        )

    def post_batch(self, data, send_resiliently=True):
        # type: (Sequence[Union[RemoteException, Attack, RequestRecord, Signal]], bool) -> None
        batch = [self._format_event(event) for event in data]  # type: ignore
        try:
            self.sender.send_batch(batch)
        except (MaxRetryError, HTTPError) as exc:
            LOGGER.error("Couldn't send batch due to exception %s", type(exc).__name__)
            self._dropped += len(batch)
        else:
            self._sent += len(batch)

    def get_metrics(self, at=None):
        sent = self._sent
        dropped = self._dropped
        self._sent = 0
        self._dropped = 0
        at = at or now()
        return [
            ("event_manager", at, "backend_egress", sent),
            ("event_manager", at, "backend_dropped", dropped),
        ]


class Session(object):
    """ Class responsible for collection date and interacting with the sqreen API
    """

    ingestion_sender_class = sender.Sender

    def __init__(self, connection, api_key, app_name=None, use_signals=False,
                 ingestion_url=None):
        self.connection = connection
        self.api_key = api_key
        self.app_name = app_name
        self.session_token = None
        self.ingestion_url = ingestion_url
        self.use_signals = use_signals

    def get_use_signals(self):
        return isinstance(self.delegate, IngestionEvents)

    def set_use_signals(self, value):
        """ Set Signal Ingestion
        """
        if not value:
            self.delegate = LegacyEvents(self)
            return

        if self.ingestion_url is None:
            if self.connection.use_legacy_url:
                self.ingestion_url = CONFIG["LEGACY_URL"]
            else:
                self.ingestion_url = CONFIG["INGESTION_URL"]

        headers = self._headers()
        headers["User-Agent"] = self.connection.user_agent

        self.delegate = IngestionEvents(self.ingestion_sender_class(
            base_url=self.ingestion_url,
            proxy_url=self.connection.proxy_url,
            headers=headers
        ))

    use_signals = property(get_use_signals, set_use_signals)

    def login(self, runtime_infos, retries=None):
        """ Login to the backend
        """

        if not retries:
            retries = self.connection.RETRY

        # We want repeat this logic for as long as necessary, but want to avoid a recursive call
        try:
            result = self.connection.post(
                "v1/app-login", runtime_infos, headers=self._api_headers(),
                retries=retries
            )
        except InvalidStatusCodeResponse as exc:
            LOGGER.error(
                "Cannot login. Token may be invalid: %s", self.api_key
            )
            LOGGER.error("Invalid response: %s", exc.response_data)
            if exc.status in (401, 403):
                raise InvalidToken
            raise
        except StatusFailedResponse as exc:
            LOGGER.error(
                "Cannot login. Token may be invalid: %s", self.api_key
            )
            LOGGER.error("Invalid response: %s", exc.response)
            raise InvalidToken
        except (SqreenException, HTTPError) as exc:
            LOGGER.error(
                "Cannot login. back.sqreen.io appears to be unavailable (%s).", type(exc).__name__
            )
            raise HTTPError

        LOGGER.debug("Received session_id %s", result["session_id"])
        self.session_token = result["session_id"]

        return result

    def is_connected(self):
        """ Return a boolean indicating if a successfull login was made
        """
        return self.session_token is not None

    def _headers(self):
        """Return session headers used for authentication."""
        return {"x-session-key": self.session_token}

    def _api_headers(self):
        """Return API headers."""
        if self.app_name:
            return {
                "x-api-key": self.api_key,
                "x-app-name": self.app_name
            }
        else:
            return {
                "x-api-key": self.api_key
            }

    def perform_network(self, net_operation, url, retries, payload=None, headers=None, last_resort=False):
        """ Perform a network operation safely
        """
        try:
            if headers is None:
                headers = self._headers()

            if payload is None:
                return net_operation(url, headers=headers, retries=retries)
            else:
                return net_operation(url, payload, headers=headers, retries=retries)

        except MaxRetryError:
            LOGGER.info(
                "Request to %s expired after %d retries, moving on", url, retries.total
            )

        except InvalidStatusCodeResponse as exc:
            if exc.status in (401, 403):
                raise InvalidSession
            LOGGER.info("Unexpected HTTP status code: %r", exc.status)

        except (SqreenException, HTTPError) as exc:
            LOGGER.info(
                "Couldn't connect to %s due to exception %s", url, type(exc).__name__
            )
            # Prevent recursive exception
            if not last_resort:
                self.post_sqreen_exception(RemoteException.from_exc_info(), last_resort=True)

    def _get(self, url, retries=None):
        """ Call connection.get with right headers
        """
        return self.perform_network(self.connection.get, url=url, retries=retries)

    def _post(self, url, data, retries=None, last_resort=False):
        """Call connection.post with session headers."""
        return self.perform_network(self.connection.post, payload=data, url=url, retries=retries, last_resort=last_resort)

    def _post_api(self, url, data, retries=None):
        """Call connection.post with API headers."""
        return self.perform_network(self.connection.post, payload=data, url=url, headers=self._api_headers(), retries=retries)

    def logout(self):
        # type: () -> Optional[Mapping]
        """ Logout current instance in the backend
        """
        return self._get("v0/app-logout", retries=self.connection.RETRY_ONCE)

    def heartbeat(self, payload):
        # type: (Mapping) -> Optional[Mapping]
        """ Tell the backend that the instance is still up, send latests command
        result, latest metrics and retrieve latest commands
        """
        return self._post(
            "v1/app-beat", payload, retries=self.connection.RETRY_LONG
        )

    def get_rulespack(self):
        # type: () -> Optional[Mapping]
        """ Retrieve rulespack from backend
        """
        return self._get("v0/rulespack", retries=self.connection.RETRY_LONG)

    def post_bundle(self, runtime_infos):
        # type: (MutableMapping) -> Optional[Mapping]
        data = {
            "bundle_signature": runtime_infos["bundle_signature"],
            "dependencies": runtime_infos["various_infos"]["dependencies"],
        }
        return self._post(
            "v0/bundle", data, retries=self.connection.RETRY_LONG
        )

    def get_actionspack(self):
        # type: () -> Optional[Mapping]
        """Retrieve actions from backend."""
        return self._get("v0/actionspack", retries=self.connection.RETRY_LONG)

    def post_app_sqreen_exception(self, exception):
        # type: (RemoteException) -> Optional[Mapping]
        """ Post a sqreen exception happening at application level."""
        return self._post_api(
            "v0/app_sqreen_exception", exception.to_dict(),
            retries=self.connection.RETRY_ONCE
        )

    # Proxy methods to delegate

    def post_signal(self, signal):
        # type: (Signal) -> Optional[Mapping]
        """ Report a signal to the backend
        """
        LOGGER.debug("Post signal %r", signal)
        return self.delegate.post_signal(signal)

    def post_attack(self, attack):
        # type: (Attack) -> Optional[Mapping]
        """ Report an attack to the backend
        """
        LOGGER.debug("Post attack %r", attack)
        return self.delegate.post_attack(attack)

    def post_sqreen_exception(self, exception, last_resort=False):
        # type: (RemoteException, bool) -> Optional[Mapping]
        """ Report a Sqreen exception happening at agent level."""
        LOGGER.debug("Post exception %r", exception)
        return self.delegate.post_sqreen_exception(exception, last_resort=last_resort)

    def post_metrics(self, metrics):
        # type: (Sequence[Mapping]) -> Optional[Mapping]
        """ Post metrics aggregates to the backend
        """
        LOGGER.debug("Post %d metrics", len(metrics))
        return self.delegate.post_metrics(metrics)

    def post_request_record(self, request_record):
        # type: (RequestRecord) -> Optional[Mapping]
        """ Post a request record to the backend
        """
        LOGGER.debug("Post request record %r", request_record)
        return self.delegate.post_request_record(request_record)

    def post_batch(self, batch, send_resiliently=True):
        # type: (Sequence[Union[RemoteException, Attack, RequestRecord, Signal]], bool) -> Optional[Mapping]
        """ Post a batch to the backend
        """
        LOGGER.debug("Post batch of size %d", len(batch))
        return self.delegate.post_batch(batch, send_resiliently=send_resiliently)

    def get_metrics(self, at=None):
        """ Get the current session metrics
        """
        at = at or now()
        return self.delegate.get_metrics(at)
