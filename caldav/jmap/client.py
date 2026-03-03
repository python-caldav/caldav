"""
Synchronous JMAP client.

Wraps session establishment, HTTP communication, and method dispatching
into a single object with a clean public API.

Auth note: JMAP has no 401-challenge-retry dance (unlike CalDAV).
Credentials are sent upfront on every request. A 401/403 is a hard failure.
"""

from __future__ import annotations

import logging
import uuid

try:
    import niquests as requests
    from niquests.auth import HTTPBasicAuth
except ImportError:
    import requests  # type: ignore[no-redef]
    from requests.auth import HTTPBasicAuth  # type: ignore[no-redef]

from caldav.jmap._methods.calendar import build_calendar_get, parse_calendar_get
from caldav.jmap._methods.event import (
    build_event_changes,
    build_event_get,
    build_event_query,
    build_event_set_create,
    build_event_set_destroy,
    build_event_set_update,
    parse_event_changes,
    parse_event_get,
    parse_event_set,
)
from caldav.jmap._methods.task import (
    build_task_get,
    build_task_list_get,
    build_task_set_create,
    build_task_set_destroy,
    build_task_set_update,
    parse_task_list_get,
    parse_task_set,
)
from caldav.jmap.constants import CALENDAR_CAPABILITY, CORE_CAPABILITY, TASK_CAPABILITY
from caldav.jmap.convert import ical_to_jscal
from caldav.jmap.error import JMAPAuthError, JMAPMethodError
from caldav.jmap.objects.calendar import JMAPCalendar
from caldav.jmap.objects.calendar_object import JMAPCalendarObject
from caldav.jmap.session import Session, fetch_session
from caldav.requests import HTTPBearerAuth

log = logging.getLogger("caldav.jmap")

_DEFAULT_USING = [CORE_CAPABILITY, CALENDAR_CAPABILITY]
_TASK_USING = [CORE_CAPABILITY, TASK_CAPABILITY]


class _JMAPClientBase:
    def __init__(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        auth=None,
        auth_type: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout
        self._session_cache: Session | None = None

        if auth is not None:
            self._auth = auth
        else:
            self._auth = self._build_auth(auth_type)

    def _build_auth(self, auth_type: str | None):
        """Select and construct the auth object.

        **The JMAP support is experimental, the API may change in minor-releases**

        JMAP supports Basic and Bearer auth; Digest is not supported.
        When ``auth_type`` is ``None`` the type is inferred from the
        credentials supplied: a username triggers Basic, a password
        alone triggers Bearer, and neither raises :class:`JMAPAuthError`.
        """
        effective_type = auth_type
        if effective_type is None:
            if self.username:
                effective_type = "basic"
            elif self.password:
                effective_type = "bearer"
            else:
                raise JMAPAuthError(
                    url=self.url,
                    reason="No credentials provided. Supply username+password or a bearer token.",
                )

        if effective_type == "basic":
            if not self.username or not self.password:
                raise JMAPAuthError(
                    url=self.url,
                    reason="Basic auth requires both username and password.",
                )
            return HTTPBasicAuth(self.username, self.password)
        elif effective_type == "bearer":
            if not self.password:
                raise JMAPAuthError(
                    url=self.url,
                    reason="Bearer auth requires a token supplied as the password argument.",
                )
            return HTTPBearerAuth(self.password)
        else:
            raise JMAPAuthError(
                url=self.url,
                reason=f"Unsupported auth_type {effective_type!r}. Use 'basic' or 'bearer'.",
            )

    def _raise_set_error(self, session: Session, err: dict) -> None:
        raise JMAPMethodError(
            url=session.api_url,
            reason=f"set failed: {err}",
            error_type=err.get("type", "serverError"),
        )

    @staticmethod
    def _build_event_search_calls(
        account_id: str,
        calendar_id: str | None,
        start: str | None,
        end: str | None,
        text: str | None,
    ) -> list[tuple]:
        """Return a batched [CalendarEvent/query, CalendarEvent/get] call list for _search."""
        filter_dict: dict = {}
        if calendar_id is not None:
            filter_dict["inCalendars"] = [calendar_id]
        if start is not None:
            filter_dict["after"] = start
        if end is not None:
            filter_dict["before"] = end
        if text is not None:
            filter_dict["text"] = text
        query_call = build_event_query(account_id, filter_condition=filter_dict or None)
        get_call = (
            "CalendarEvent/get",
            {
                "accountId": account_id,
                "#ids": {
                    "resultOf": "ev-query-0",
                    "name": "CalendarEvent/query",
                    "path": "/ids",
                },
            },
            "ev-get-1",
        )
        return [query_call, get_call]


class JMAPClient(_JMAPClientBase):
    """Synchronous JMAP client for calendar operations.

    Usage::

        from caldav.jmap import get_jmap_client
        client = get_jmap_client(url="https://jmap.example.com/.well-known/jmap",
                                  username="alice", password="secret")
        calendars = client.get_calendars()

    Args:
        url: URL of the JMAP session endpoint (``/.well-known/jmap``).
        username: Username for Basic auth.
        password: Password for Basic auth, or bearer token if no username.
        auth: A pre-built requests-compatible auth object. Takes precedence
              over username/password if provided.
        auth_type: Force a specific auth type: ``"basic"`` or ``"bearer"``.
        timeout: HTTP request timeout in seconds.
    """

    def __enter__(self) -> JMAPClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    def _get_session(self) -> Session:
        """Return the cached Session, fetching it on first call."""
        if self._session_cache is None:
            self._session_cache = fetch_session(self.url, auth=self._auth, timeout=self.timeout)
        return self._session_cache

    def _request(self, method_calls: list[tuple], using: list[str] | None = None) -> list:
        """POST a batch of JMAP method calls and return the methodResponses.

        Args:
            method_calls: List of 3-tuples ``(method_name, args_dict, call_id)``.
            using: Capability URN list for the ``using`` field. Defaults to
                ``_DEFAULT_USING`` (core + calendars).

        Returns:
            List of 3-tuples ``(method_name, response_args, call_id)`` from
            the server's ``methodResponses`` array.

        Raises:
            JMAPAuthError: On HTTP 401 or 403.
            JMAPMethodError: If any methodResponse is an ``error`` response.
            requests.HTTPError: On other non-2xx HTTP responses.
        """
        session = self._get_session()

        payload = {
            "using": using if using is not None else _DEFAULT_USING,
            "methodCalls": list(method_calls),
        }

        log.debug("JMAP POST to %s: %d method call(s)", session.api_url, len(method_calls))

        response = requests.post(
            session.api_url,
            json=payload,
            auth=self._auth,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=self.timeout,
        )

        if response.status_code in (401, 403):
            raise JMAPAuthError(
                url=session.api_url,
                reason=f"HTTP {response.status_code} from API endpoint",
            )

        response.raise_for_status()

        data = response.json()
        method_responses = data.get("methodResponses", [])

        for resp in method_responses:
            method_name, resp_args, call_id = resp
            if method_name == "error":
                error_type = resp_args.get("type", "serverError")
                raise JMAPMethodError(
                    url=session.api_url,
                    reason=f"Method call failed: {resp_args}",
                    error_type=error_type,
                )

        return method_responses

    def get_calendars(self) -> list[JMAPCalendar]:
        """Fetch all calendars for the authenticated account.

        Returns:
            List of :class:`~caldav.jmap.objects.calendar.JMAPCalendar` objects.
        """
        session = self._get_session()
        call = build_calendar_get(session.account_id)
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "Calendar/get":
                calendars = parse_calendar_get(resp_args)
                for cal in calendars:
                    cal._client = self
                    cal._is_async = False
                return calendars

        return []

    def create_event(self, calendar_id: str, ical_str: str) -> str:
        """Create a calendar event from an iCalendar string.

        Args:
            calendar_id: The JMAP calendar ID to create the event in.
            ical_str: A VCALENDAR string representing the event.

        Returns:
            The server-assigned JMAP event ID.

        Raises:
            JMAPMethodError: If the server rejects the create request.
        """
        session = self._get_session()
        jscal = ical_to_jscal(ical_str, calendar_id=calendar_id)
        call = build_event_set_create(session.account_id, {"new-0": jscal})
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/set":
                created, _, _, not_created, _, _ = parse_event_set(resp_args)
                if "new-0" in not_created:
                    self._raise_set_error(session, not_created["new-0"])
                if "new-0" not in created:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason="CalendarEvent/set response missing created entry for new-0",
                    )
                return created["new-0"]["id"]

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/set response")

    def get_event(self, event_id: str) -> JMAPCalendarObject:
        """Fetch a calendar event by JMAP event ID.

        Args:
            event_id: The JMAP event ID to retrieve.

        Returns:
            A :class:`~caldav.jmap.objects.calendar_object.JMAPCalendarObject`
            wrapping the raw JSCalendar dict.  ``parent`` is ``None`` since
            no :class:`~caldav.jmap.objects.calendar.JMAPCalendar` is available
            at the client level.

        Raises:
            JMAPMethodError: If the event is not found.
        """
        session = self._get_session()
        call = build_event_get(session.account_id, ids=[event_id])
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                items = parse_event_get(resp_args)
                if not items:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason=f"Event not found: {event_id}",
                        error_type="notFound",
                    )
                return JMAPCalendarObject(data=items[0], parent=None)

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/get response")

    def update_event(self, event_id: str, ical_str: str) -> None:
        """Update a calendar event from an iCalendar string.

        Args:
            event_id: The JMAP event ID to update.
            ical_str: A VCALENDAR string with the updated event data.

        Raises:
            JMAPMethodError: If the server rejects the update.
        """
        session = self._get_session()
        patch = ical_to_jscal(ical_str)
        patch.pop("uid", None)  # uid is server-immutable after creation; patch must omit it
        call = build_event_set_update(session.account_id, {event_id: patch})
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/set":
                _, _, _, _, not_updated, _ = parse_event_set(resp_args)
                if event_id in not_updated:
                    self._raise_set_error(session, not_updated[event_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/set response")

    def _search(
        self,
        calendar_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        text: str | None = None,
        parent: JMAPCalendar | None = None,
    ) -> list[JMAPCalendarObject]:
        session = self._get_session()
        calls = self._build_event_search_calls(session.account_id, calendar_id, start, end, text)
        responses = self._request(calls)

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                return [
                    JMAPCalendarObject(data=item, parent=parent)
                    for item in parse_event_get(resp_args)
                ]

        return []

    def search_events(
        self,
        calendar_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        text: str | None = None,
    ) -> list[JMAPCalendarObject]:
        """Search for calendar events.

        All parameters are optional; omitting all returns every event in the account.
        Results are fetched in a single batched JMAP request using a result reference
        from ``CalendarEvent/query`` into ``CalendarEvent/get``.

        Args:
            calendar_id: Limit results to this calendar.
            start: Only events ending after this datetime (``YYYY-MM-DDTHH:MM:SS``).
            end: Only events starting before this datetime (``YYYY-MM-DDTHH:MM:SS``).
            text: Free-text search across title, description, locations, and participants.

        Returns:
            List of :class:`~caldav.jmap.objects.calendar_object.JMAPCalendarObject`
            instances.  ``parent`` is ``None`` on these objects since no
            :class:`~caldav.jmap.objects.calendar.JMAPCalendar` is available at
            the client level; use :meth:`JMAPCalendar.search` if you need ``parent``
            set.
        """
        return self._search(calendar_id=calendar_id, start=start, end=end, text=text)

    def get_sync_token(self) -> str:
        """Return the current CalendarEvent state string for use as a sync token.

        Calls ``CalendarEvent/get`` with an empty ID list — no event data is
        transferred, only the ``state`` field from the response.

        Returns:
            Opaque state string. Pass to :meth:`get_objects_by_sync_token` to
            retrieve only what changed since this point.
        """
        session = self._get_session()
        call = build_event_get(session.account_id, ids=[])
        responses = self._request([call])
        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                return resp_args.get("state", "")
        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/get response")

    def get_objects_by_sync_token(
        self, sync_token: str
    ) -> tuple[list[JMAPCalendarObject], list[JMAPCalendarObject], list[str]]:
        """Fetch events changed since a previous sync token.

        Calls ``CalendarEvent/changes`` to discover which events were created,
        modified, or destroyed since ``sync_token`` was issued. Created and
        modified events are returned as
        :class:`~caldav.jmap.objects.calendar_object.JMAPCalendarObject` instances;
        destroyed events are returned as IDs (the objects no longer exist on the server).

        Args:
            sync_token: A state string previously returned by :meth:`get_sync_token`
                or by a prior call to this method.

        Returns:
            A 3-tuple ``(added, modified, deleted)``:

            - ``added``: objects for newly created events (``parent`` is ``None``).
            - ``modified``: objects for updated events (``parent`` is ``None``).
            - ``deleted``: Event IDs that were destroyed.

        Raises:
            JMAPMethodError: If the server reports ``hasMoreChanges: true``.
        """
        session = self._get_session()
        changes_call = build_event_changes(session.account_id, sync_token)
        responses = self._request([changes_call])

        created_ids: list[str] = []
        updated_ids: list[str] = []
        destroyed: list[str] = []

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/changes":
                _, _, has_more, created_ids, updated_ids, destroyed = parse_event_changes(resp_args)
                if has_more:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason=(
                            "CalendarEvent/changes response was truncated by the server "
                            "(hasMoreChanges=true). Call get_sync_token() to obtain a "
                            "fresh baseline and re-sync."
                        ),
                        error_type="serverPartialFail",
                    )

        fetch_ids = created_ids + updated_ids
        if not fetch_ids:
            return [], [], destroyed

        get_call = build_event_get(session.account_id, ids=fetch_ids)
        get_responses = self._request([get_call])

        events_by_id: dict[str, JMAPCalendarObject] = {}
        for method_name, resp_args, _ in get_responses:
            if method_name == "CalendarEvent/get":
                for item in parse_event_get(resp_args):
                    events_by_id[item["id"]] = JMAPCalendarObject(data=item, parent=None)

        added = [events_by_id[i] for i in created_ids if i in events_by_id]
        modified = [events_by_id[i] for i in updated_ids if i in events_by_id]
        return added, modified, destroyed

    def delete_event(self, event_id: str) -> None:
        """Delete a calendar event.

        Args:
            event_id: The JMAP event ID to delete.

        Raises:
            JMAPMethodError: If the server rejects the delete.
        """
        session = self._get_session()
        call = build_event_set_destroy(session.account_id, [event_id])
        responses = self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/set":
                _, _, _, _, _, not_destroyed = parse_event_set(resp_args)
                if event_id in not_destroyed:
                    self._raise_set_error(session, not_destroyed[event_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/set response")

    def _get_object_by_uid(
        self, uid: str, calendar_id: str | None = None, parent: JMAPCalendar | None = None
    ) -> JMAPCalendarObject:
        # RFC 8984 FilterCondition has no uid field; UID matching is done client-side.
        for obj in self._search(calendar_id=calendar_id, parent=parent):
            if obj.data.get("uid") == uid:
                return obj

        raise JMAPMethodError(
            url=self._get_session().api_url, reason=f"No calendar object found with UID: {uid}"
        )

    def get_task_lists(self) -> list[dict]:
        """Fetch all task lists for the authenticated account.

        Returns:
            List of raw JMAP TaskList dicts as returned by the server.
        """
        session = self._get_session()
        call = build_task_list_get(session.account_id)
        responses = self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "TaskList/get":
                return parse_task_list_get(resp_args)

        return []

    def create_task(self, task_list_id: str, title: str, **kwargs) -> str:
        """Create a task in a task list.

        Args:
            task_list_id: The JMAP task list ID to create the task in.
            title: Task title (maps to VTODO ``SUMMARY``).
            **kwargs: Optional JMAP Task fields using wire names: ``description``,
                ``due``, ``start``, ``timeZone``, ``estimatedDuration``,
                ``percentComplete``, ``progress``, ``priority``.

        Returns:
            The server-assigned JMAP task ID.

        Raises:
            JMAPMethodError: If the server rejects the create request.
        """
        session = self._get_session()
        task_dict = {
            "@type": "Task",
            "uid": str(uuid.uuid4()),
            "taskListId": task_list_id,
            "title": title,
            "percentComplete": 0,
            "progress": "needs-action",
            "priority": 0,
        }
        task_dict.update(kwargs)
        call = build_task_set_create(session.account_id, {"new-0": task_dict})
        responses = self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                created, _, _, not_created, _, _ = parse_task_set(resp_args)
                if "new-0" in not_created:
                    self._raise_set_error(session, not_created["new-0"])
                return created["new-0"]["id"]

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")

    def get_task(self, task_id: str) -> dict:
        """Fetch a task by ID.

        Args:
            task_id: The JMAP task ID to retrieve.

        Returns:
            Raw JMAP Task dict as returned by the server.

        Raises:
            JMAPMethodError: If the task is not found.
        """
        session = self._get_session()
        call = build_task_get(session.account_id, ids=[task_id])
        responses = self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/get":
                items = resp_args.get("list", [])
                if not items:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason=f"Task not found: {task_id}",
                        error_type="notFound",
                    )
                return items[0]

        raise JMAPMethodError(url=session.api_url, reason="No Task/get response")

    def update_task(self, task_id: str, patch: dict) -> None:
        """Update a task with a partial patch.

        Args:
            task_id: The JMAP task ID to update.
            patch: Partial patch dict mapping property names to new values.

        Raises:
            JMAPMethodError: If the server rejects the update.
        """
        session = self._get_session()
        call = build_task_set_update(session.account_id, {task_id: patch})
        responses = self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                _, _, _, _, not_updated, _ = parse_task_set(resp_args)
                if task_id in not_updated:
                    self._raise_set_error(session, not_updated[task_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")

    def delete_task(self, task_id: str) -> None:
        """Delete a task.

        Args:
            task_id: The JMAP task ID to delete.

        Raises:
            JMAPMethodError: If the server rejects the delete.
        """
        session = self._get_session()
        call = build_task_set_destroy(session.account_id, [task_id])
        responses = self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                _, _, _, _, _, not_destroyed = parse_task_set(resp_args)
                if task_id in not_destroyed:
                    self._raise_set_error(session, not_destroyed[task_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")
