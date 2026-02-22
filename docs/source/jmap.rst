====
JMAP
====

The caldav library includes a JMAP client for servers that speak
`RFC 8620 <https://www.rfc-editor.org/rfc/rfc8620>`_ (JMAP Core) and
`RFC 8984 <https://www.rfc-editor.org/rfc/rfc8984>`_ (JMAP Calendars).
It covers calendar listing, event CRUD, incremental sync, and task CRUD — the same
operations as the CalDAV client — so the choice of protocol comes down to what the
server supports.

.. note::

   The JMAP client targets servers implementing
   ``urn:ietf:params:jmap:calendars``.  Cyrus IMAP is the primary tested server.
   Task support (``urn:ietf:params:jmap:tasks``) requires a separate server
   capability; Cyrus does not implement it yet.

Quick Start
===========

.. code-block:: python

    from caldav.jmap import get_jmap_client

    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    )
    calendars = client.get_calendars()
    for cal in calendars:
        print(cal.name)

:func:`~caldav.jmap.get_jmap_client` reads configuration from the same sources
as :func:`caldav.get_davclient`: explicit keyword arguments, then the
``CALDAV_URL`` / ``CALDAV_USERNAME`` / ``CALDAV_PASSWORD`` environment variables,
then a config file.  If none of those are set it returns ``None``.

With environment variables or a config file in place, no arguments are needed:

.. code-block:: python

    client = get_jmap_client()   # reads env vars or config file

Authentication
==============

HTTP Basic auth is used when a ``username`` is supplied alongside a ``password``.
Bearer token auth is used when only a ``password`` (token) is given and no username.
You can also pass any ``requests``-compatible auth object directly via the ``auth``
parameter (niquests is API-compatible with requests).

.. code-block:: python

    # Basic auth
    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    )

    # Bearer token (password argument holds the token; no username supplied)
    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        password="my-bearer-token",
    )

    # Pre-built auth object
    try:
        from niquests.auth import HTTPBasicAuth
    except ImportError:
        from requests.auth import HTTPBasicAuth
    client = get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        auth=HTTPBasicAuth("alice", "secret"),
    )

Unlike CalDAV, JMAP does not use a 401-challenge-retry dance — credentials are sent
on every request, and a 401 or 403 is a hard :class:`~caldav.jmap.error.JMAPAuthError`.

Context manager usage is supported but not required — no persistent TCP connection is
held between calls (the JMAP Session object is cached after the first request, but
that is just a JSON document, not a socket):

.. code-block:: python

    with get_jmap_client(...) as client:
        calendars = client.get_calendars()

Listing Calendars
=================

.. code-block:: python

    calendars = client.get_calendars()
    for cal in calendars:
        print(cal.id, cal.name, cal.color)

Each item is a :class:`~caldav.jmap.objects.calendar.JMAPCalendar` dataclass.
The fields are ``id``, ``name``, ``description``, ``color`` (CSS string or ``None``),
``is_subscribed``, ``my_rights`` (dict), ``sort_order``, and ``is_visible``.

Working with Events
===================

Events are passed as iCalendar strings — the same format used by the CalDAV client
— so existing iCalendar-producing code works unchanged.

To create an event, pass a VCALENDAR string and the target calendar ID:

.. code-block:: python

    ical = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//example//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:meeting-2026-01-15@example.com\r\n"
        "SUMMARY:Team meeting\r\n"
        "DTSTART:20260115T100000Z\r\n"
        "DTEND:20260115T110000Z\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    calendar_id = calendars[0].id
    event_id = client.create_event(calendar_id, ical)

The return value is the server-assigned JMAP event ID (a string).  You can fetch the
event back as a VCALENDAR string, update it by passing a new VCALENDAR string, or
delete it:

.. code-block:: python

    # Fetch — returns a VCALENDAR string
    ical_str = client.get_event(event_id)

    # Update — pass a complete VCALENDAR string with the changes applied
    updated = ical_str.replace("Team meeting", "Team standup")
    client.update_event(event_id, updated)

    # Delete
    client.delete_event(event_id)

Searching Events
================

.. code-block:: python

    # All events in a specific calendar
    results = client.search_events(calendar_id=calendar_id)

    # Time-range filter: events that overlap [start, end)
    #   start — only events ending after this datetime
    #   end   — only events starting before this datetime
    results = client.search_events(
        calendar_id=calendar_id,
        start="2026-01-01T00:00:00",
        end="2026-02-01T00:00:00",
    )

    # Free-text search across title, description, locations, and participants
    results = client.search_events(text="standup")

    for ical_str in results:
        print(ical_str)

All parameters are optional; omitting all returns every event visible to the account.
Results are returned as a list of VCALENDAR strings.  The search uses a single batched
JMAP request (``CalendarEvent/query`` + result reference into ``CalendarEvent/get``),
so only one HTTP round-trip is made regardless of how many events match.

Incremental Sync
================

JMAP's state-based sync lets you fetch only what changed since the last call, without
scanning the full calendar:

.. code-block:: python

    # Record the current state
    token = client.get_sync_token()

    # ... time passes, events are created/modified/deleted ...

    # Fetch only the delta
    added, modified, deleted = client.get_objects_by_sync_token(token)

    for ical_str in added:
        print("New:", ical_str)
    for ical_str in modified:
        print("Updated:", ical_str)
    for event_id in deleted:
        print("Deleted ID:", event_id)

``added`` and ``modified`` are lists of VCALENDAR strings.  ``deleted`` is a list
of event IDs — the objects no longer exist on the server, so their data cannot be
fetched.

:meth:`~caldav.jmap.client.JMAPClient.get_objects_by_sync_token` raises
:class:`~caldav.jmap.error.JMAPMethodError` (``error_type="serverPartialFail"``) if
the server truncated the change list (``hasMoreChanges: true``).  If this happens,
call :meth:`~caldav.jmap.client.JMAPClient.get_sync_token` to establish a fresh
baseline and re-sync from scratch.

A typical pattern is to persist the token between runs:

.. code-block:: python

    import json
    import pathlib

    TOKEN_FILE = pathlib.Path("sync_token.json")

    def load_token():
        if TOKEN_FILE.exists():
            return json.loads(TOKEN_FILE.read_text())["token"]
        return None

    def save_token(token):
        TOKEN_FILE.write_text(json.dumps({"token": token}))

    token = load_token()
    if token is None:
        token = client.get_sync_token()
        save_token(token)
    else:
        added, modified, deleted = client.get_objects_by_sync_token(token)
        # process changes ...
        token = client.get_sync_token()
        save_token(token)

Tasks
=====

Task support requires a server implementing ``urn:ietf:params:jmap:tasks``
(RFC 9553).  If the server does not support this capability,
:meth:`~caldav.jmap.client.JMAPClient.get_task_lists` will raise
:class:`~caldav.jmap.error.JMAPMethodError`.

.. code-block:: python

    # List task lists
    task_lists = client.get_task_lists()
    for tl in task_lists:
        print(tl.id, tl.name)

    task_list_id = task_lists[0].id

    # Create a task — title is required; everything else is optional
    task_id = client.create_task(
        task_list_id,
        title="Review pull request",
        due="2026-02-15T17:00:00",
        time_zone="Europe/Oslo",
    )

    # Fetch — returns a JMAPTask dataclass
    task = client.get_task(task_id)
    print(task.title)          # str
    print(task.progress)       # "needs-action" (default)
    print(task.percent_complete)  # 0 (default)

    # Update — pass a partial patch dict using JMAP wire property names
    client.update_task(task_id, {"progress": "completed", "percentComplete": 100})

    # Delete
    client.delete_task(task_id)

Optional kwargs for :meth:`~caldav.jmap.client.JMAPClient.create_task`:
``description``, ``start``, ``due``, ``time_zone``, ``estimated_duration``,
``percent_complete``, ``progress``, ``priority``.

Each item from :meth:`~caldav.jmap.client.JMAPClient.get_task` is a
:class:`~caldav.jmap.objects.task.JMAPTask` with fields ``id``, ``uid``,
``task_list_id``, ``title``, ``description``, ``start``, ``due``, ``time_zone``,
``estimated_duration``, ``percent_complete``, ``progress``, ``progress_updated``,
``priority``, ``is_draft``, ``keywords``, ``recurrence_rules``,
``recurrence_overrides``, ``alerts``, ``participants``, ``color``, ``privacy``.

Each item from :meth:`~caldav.jmap.client.JMAPClient.get_task_lists` is a
:class:`~caldav.jmap.objects.task.JMAPTaskList` with fields ``id``, ``name``,
``description``, ``color``, ``is_subscribed``, ``my_rights``, ``sort_order``,
``time_zone``, ``role`` (``"inbox"``, ``"trash"``, or ``None``).

Async API
=========

:class:`~caldav.jmap.async_client.AsyncJMAPClient` mirrors every method of
:class:`~caldav.jmap.client.JMAPClient` as a coroutine.  Use it as an
``async with`` context manager (sync ``with`` is not supported):

.. code-block:: python

    import asyncio
    from caldav.jmap import get_async_jmap_client

    async def main():
        async with get_async_jmap_client(
            url="https://jmap.example.com/.well-known/jmap",
            username="alice",
            password="secret",
        ) as client:
            calendars = await client.get_calendars()
            for cal in calendars:
                print(cal.name)

    asyncio.run(main())

All methods — event CRUD, search, sync, and task operations — are available as
coroutines with identical signatures.  The async client uses ``niquests.AsyncSession``
internally; ``niquests`` is a required dependency.

Error Handling
==============

All JMAP errors extend :class:`~caldav.jmap.error.JMAPError`, which itself extends
:class:`~caldav.lib.error.DAVError`.  Existing CalDAV error handlers will catch JMAP
errors too if they catch ``DAVError``.

.. code-block:: python

    from caldav.lib.error import DAVError
    from caldav.jmap.error import JMAPAuthError, JMAPCapabilityError, JMAPMethodError

    try:
        event_id = client.create_event(calendar_id, ical)
    except JMAPAuthError:
        print("Authentication failed (401/403)")
    except JMAPCapabilityError:
        print("Server does not support urn:ietf:params:jmap:calendars")
    except JMAPMethodError as e:
        print(f"Server rejected the request: {e.error_type} — {e.reason}")
    except DAVError as e:
        print(f"Protocol error: {e}")

The three specific error classes:

* :class:`~caldav.jmap.error.JMAPAuthError` — HTTP 401 or 403.  JMAP sends no
  401-challenge, so this is always a hard failure.
* :class:`~caldav.jmap.error.JMAPCapabilityError` — the server's Session object
  does not advertise ``urn:ietf:params:jmap:calendars``.
* :class:`~caldav.jmap.error.JMAPMethodError` — a JMAP method call returned an error
  response.  The ``error_type`` attribute holds the RFC 8620 error type string
  (e.g. ``"invalidArguments"``, ``"notFound"``, ``"stateMismatch"``).

Configuration File
==================

The JMAP client reads from the same configuration file as the CalDAV client.
Connection parameters use the ``caldav_`` prefix:

.. code-block:: yaml

   ---
   default:
       caldav_url: https://jmap.example.com/.well-known/jmap
       caldav_username: alice
       caldav_password: secret

With the file in place, no arguments are needed:

.. code-block:: python

    client = get_jmap_client()

See :doc:`configfile` for file locations, section inheritance, and other options.

API Reference
=============

* :doc:`caldav/jmap_client` — :class:`~caldav.jmap.client.JMAPClient` and
  :class:`~caldav.jmap.async_client.AsyncJMAPClient` full method reference
* :doc:`caldav/jmap_objects` — :class:`~caldav.jmap.objects.calendar.JMAPCalendar`,
  :class:`~caldav.jmap.objects.event.JMAPEvent`,
  :class:`~caldav.jmap.objects.task.JMAPTask`,
  :class:`~caldav.jmap.objects.task.JMAPTaskList`, and error classes
