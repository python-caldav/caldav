"""
Asynchronous JMAP client.

Mirrors JMAPClient with all public methods as coroutines.
Uses niquests.AsyncSession for HTTP — niquests is a core dependency.
"""

from __future__ import annotations

import logging
import uuid

from niquests import AsyncSession

from caldav.jmap.client import _DEFAULT_USING, _TASK_USING, _JMAPClientBase
from caldav.jmap.convert import ical_to_jscal, jscal_to_ical
from caldav.jmap.error import JMAPAuthError, JMAPMethodError
from caldav.jmap.methods.calendar import build_calendar_get, parse_calendar_get
from caldav.jmap.methods.event import (
    build_event_changes,
    build_event_get,
    build_event_query,
    build_event_set_destroy,
    build_event_set_update,
    parse_event_changes,
    parse_event_set,
)
from caldav.jmap.methods.task import (
    build_task_get,
    build_task_list_get,
    build_task_set_create,
    build_task_set_destroy,
    build_task_set_update,
    parse_task_list_get,
    parse_task_set,
)
from caldav.jmap.objects.calendar import JMAPCalendar
from caldav.jmap.objects.task import JMAPTask, JMAPTaskList
from caldav.jmap.session import Session, async_fetch_session

log = logging.getLogger("caldav.jmap")


class AsyncJMAPClient(_JMAPClientBase):
    """Asynchronous JMAP client for calendar operations.

    Usage::

        from caldav.jmap import get_async_jmap_client
        async with get_async_jmap_client(url="https://jmap.example.com/.well-known/jmap",
                                          username="alice", password="secret") as client:
            calendars = await client.get_calendars()

    Args:
        url: URL of the JMAP session endpoint (``/.well-known/jmap``).
        username: Username for Basic auth.
        password: Password for Basic auth, or bearer token if no username.
        auth: A pre-built niquests-compatible auth object. Takes precedence
              over username/password if provided.
        auth_type: Force a specific auth type: ``"basic"`` or ``"bearer"``.
        timeout: HTTP request timeout in seconds.
    """

    async def __aenter__(self) -> AsyncJMAPClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None

    async def _get_session(self) -> Session:
        """Return the cached Session, fetching it on first call."""
        if self._session_cache is None:
            self._session_cache = await async_fetch_session(
                self.url, auth=self._auth, timeout=self.timeout
            )
        return self._session_cache

    async def _request(self, method_calls: list[tuple], using: list[str] | None = None) -> list:
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
        """
        session = await self._get_session()

        payload = {
            "using": using if using is not None else _DEFAULT_USING,
            "methodCalls": list(method_calls),
        }

        log.debug("JMAP POST to %s: %d method call(s)", session.api_url, len(method_calls))

        async with AsyncSession() as http:
            response = await http.post(
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

    async def get_calendars(self) -> list[JMAPCalendar]:
        """Fetch all calendars for the authenticated account.

        Returns:
            List of :class:`~caldav.jmap.objects.calendar.JMAPCalendar` objects.
        """
        session = await self._get_session()
        call = build_calendar_get(session.account_id)
        responses = await self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "Calendar/get":
                return parse_calendar_get(resp_args)

        return []

    async def create_event(self, calendar_id: str, ical_str: str) -> str:
        """Create a calendar event from an iCalendar string.

        Args:
            calendar_id: The JMAP calendar ID to create the event in.
            ical_str: A VCALENDAR string representing the event.

        Returns:
            The server-assigned JMAP event ID.

        Raises:
            JMAPMethodError: If the server rejects the create request.
        """
        session = await self._get_session()
        jscal = ical_to_jscal(ical_str, calendar_id=calendar_id)
        call = (
            "CalendarEvent/set",
            {"accountId": session.account_id, "create": {"new-0": jscal}},
            "ev-set-create-0",
        )
        responses = await self._request([call])

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

    async def get_event(self, event_id: str) -> str:
        """Fetch a calendar event as an iCalendar string.

        Args:
            event_id: The JMAP event ID to retrieve.

        Returns:
            A VCALENDAR string for the event.

        Raises:
            JMAPMethodError: If the event is not found.
        """
        session = await self._get_session()
        call = build_event_get(session.account_id, ids=[event_id])
        responses = await self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                items = resp_args.get("list", [])
                if not items:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason=f"Event not found: {event_id}",
                        error_type="notFound",
                    )
                return jscal_to_ical(items[0])

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/get response")

    async def update_event(self, event_id: str, ical_str: str) -> None:
        """Update a calendar event from an iCalendar string.

        Args:
            event_id: The JMAP event ID to update.
            ical_str: A VCALENDAR string with the updated event data.

        Raises:
            JMAPMethodError: If the server rejects the update.
        """
        session = await self._get_session()
        patch = ical_to_jscal(ical_str)
        patch.pop("uid", None)  # uid is server-immutable after creation; patch must omit it
        call = build_event_set_update(session.account_id, {event_id: patch})
        responses = await self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/set":
                _, _, _, _, not_updated, _ = parse_event_set(resp_args)
                if event_id in not_updated:
                    self._raise_set_error(session, not_updated[event_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/set response")

    async def search_events(
        self,
        calendar_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
        text: str | None = None,
    ) -> list[str]:
        """Search for calendar events and return them as iCalendar strings.

        All parameters are optional; omitting all returns every event in the account.
        Results are fetched in a single batched JMAP request using a result reference
        from ``CalendarEvent/query`` into ``CalendarEvent/get``.

        Args:
            calendar_id: Limit results to this calendar.
            start: Only events ending after this datetime (``YYYY-MM-DDTHH:MM:SS``).
            end: Only events starting before this datetime (``YYYY-MM-DDTHH:MM:SS``).
            text: Free-text search across title, description, locations, and participants.

        Returns:
            List of VCALENDAR strings for all matching events.
        """
        session = await self._get_session()
        filter_dict: dict = {}
        if calendar_id is not None:
            filter_dict["inCalendars"] = [calendar_id]
        if start is not None:
            filter_dict["after"] = start
        if end is not None:
            filter_dict["before"] = end
        if text is not None:
            filter_dict["text"] = text

        query_call = build_event_query(session.account_id, filter=filter_dict or None)
        get_call = (
            "CalendarEvent/get",
            {
                "accountId": session.account_id,
                "#ids": {
                    "resultOf": "ev-query-0",
                    "name": "CalendarEvent/query",
                    "path": "/ids",
                },
            },
            "ev-get-1",
        )
        responses = await self._request([query_call, get_call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                return [jscal_to_ical(item) for item in resp_args.get("list", [])]

        return []

    async def get_sync_token(self) -> str:
        """Return the current CalendarEvent state string for use as a sync token.

        Calls ``CalendarEvent/get`` with an empty ID list — no event data is
        transferred, only the ``state`` field from the response.

        Returns:
            Opaque state string. Pass to :meth:`get_objects_by_sync_token` to
            retrieve only what changed since this point.
        """
        session = await self._get_session()
        call = build_event_get(session.account_id, ids=[])
        responses = await self._request([call])
        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/get":
                return resp_args.get("state", "")
        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/get response")

    async def get_objects_by_sync_token(
        self, sync_token: str
    ) -> tuple[list[str], list[str], list[str]]:
        """Fetch events changed since a previous sync token.

        Calls ``CalendarEvent/changes`` to discover which events were created,
        modified, or destroyed since ``sync_token`` was issued. Created and
        modified events are returned as iCalendar strings; destroyed events are
        returned as IDs (the objects no longer exist on the server).

        Args:
            sync_token: A state string previously returned by :meth:`get_sync_token`
                or by a prior call to this method.

        Returns:
            A 3-tuple ``(added, modified, deleted)``:

            - ``added``: iCalendar strings for newly created events.
            - ``modified``: iCalendar strings for updated events.
            - ``deleted``: Event IDs that were destroyed.

        Raises:
            JMAPMethodError: If the server reports ``hasMoreChanges: true``.
        """
        session = await self._get_session()
        changes_call = build_event_changes(session.account_id, sync_token)
        responses = await self._request([changes_call])

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
        get_responses = await self._request([get_call])

        events_by_id: dict[str, str] = {}
        for method_name, resp_args, _ in get_responses:
            if method_name == "CalendarEvent/get":
                for item in resp_args.get("list", []):
                    events_by_id[item["id"]] = jscal_to_ical(item)

        added = [events_by_id[i] for i in created_ids if i in events_by_id]
        modified = [events_by_id[i] for i in updated_ids if i in events_by_id]
        return added, modified, destroyed

    async def delete_event(self, event_id: str) -> None:
        """Delete a calendar event.

        Args:
            event_id: The JMAP event ID to delete.

        Raises:
            JMAPMethodError: If the server rejects the delete.
        """
        session = await self._get_session()
        call = build_event_set_destroy(session.account_id, [event_id])
        responses = await self._request([call])

        for method_name, resp_args, _ in responses:
            if method_name == "CalendarEvent/set":
                _, _, _, _, _, not_destroyed = parse_event_set(resp_args)
                if event_id in not_destroyed:
                    self._raise_set_error(session, not_destroyed[event_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No CalendarEvent/set response")

    async def get_task_lists(self) -> list[JMAPTaskList]:
        """Fetch all task lists for the authenticated account.

        Returns:
            List of :class:`~caldav.jmap.objects.task.JMAPTaskList` objects.
        """
        session = await self._get_session()
        call = build_task_list_get(session.account_id)
        responses = await self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "TaskList/get":
                return parse_task_list_get(resp_args)

        return []

    async def create_task(self, task_list_id: str, title: str, **kwargs) -> str:
        """Create a task in a task list.

        Args:
            task_list_id: The JMAP task list ID to create the task in.
            title: Task title (maps to VTODO ``SUMMARY``).
            **kwargs: Optional task fields: ``description``, ``due``, ``start``,
                ``time_zone``, ``estimated_duration``, ``percent_complete``,
                ``progress``, ``priority``.

        Returns:
            The server-assigned JMAP task ID.

        Raises:
            JMAPMethodError: If the server rejects the create request.
        """
        session = await self._get_session()
        task = JMAPTask(
            id="",
            uid=str(uuid.uuid4()),
            task_list_id=task_list_id,
            title=title,
            **kwargs,
        )
        call = build_task_set_create(session.account_id, {"new-0": task})
        responses = await self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                created, _, _, not_created, _, _ = parse_task_set(resp_args)
                if "new-0" in not_created:
                    self._raise_set_error(session, not_created["new-0"])
                return created["new-0"]["id"]

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")

    async def get_task(self, task_id: str) -> JMAPTask:
        """Fetch a task by ID.

        Args:
            task_id: The JMAP task ID to retrieve.

        Returns:
            A :class:`~caldav.jmap.objects.task.JMAPTask` object.

        Raises:
            JMAPMethodError: If the task is not found.
        """
        session = await self._get_session()
        call = build_task_get(session.account_id, ids=[task_id])
        responses = await self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/get":
                items = resp_args.get("list", [])
                if not items:
                    raise JMAPMethodError(
                        url=session.api_url,
                        reason=f"Task not found: {task_id}",
                        error_type="notFound",
                    )
                return JMAPTask.from_jmap(items[0])

        raise JMAPMethodError(url=session.api_url, reason="No Task/get response")

    async def update_task(self, task_id: str, patch: dict) -> None:
        """Update a task with a partial patch.

        Args:
            task_id: The JMAP task ID to update.
            patch: Partial patch dict mapping property names to new values.

        Raises:
            JMAPMethodError: If the server rejects the update.
        """
        session = await self._get_session()
        call = build_task_set_update(session.account_id, {task_id: patch})
        responses = await self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                _, _, _, _, not_updated, _ = parse_task_set(resp_args)
                if task_id in not_updated:
                    self._raise_set_error(session, not_updated[task_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")

    async def delete_task(self, task_id: str) -> None:
        """Delete a task.

        Args:
            task_id: The JMAP task ID to delete.

        Raises:
            JMAPMethodError: If the server rejects the delete.
        """
        session = await self._get_session()
        call = build_task_set_destroy(session.account_id, [task_id])
        responses = await self._request([call], using=_TASK_USING)

        for method_name, resp_args, _ in responses:
            if method_name == "Task/set":
                _, _, _, _, _, not_destroyed = parse_task_set(resp_args)
                if task_id in not_destroyed:
                    self._raise_set_error(session, not_destroyed[task_id])
                return

        raise JMAPMethodError(url=session.api_url, reason="No Task/set response")
