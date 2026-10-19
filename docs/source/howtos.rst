=============
How-To Guides
=============

Editing Calendar Data
---------------------

Calendar objects (events, todos, journals) can be accessed and modified
using the icalendar or vobject libraries.

Reading Data
~~~~~~~~~~~~

For read-only access, use methods that return copies:

.. code-block:: python

    # Get raw iCalendar string
    data = event.get_data()

    # Get icalendar object (a copy - safe to inspect)
    ical = event.get_icalendar_instance()
    for comp in ical.subcomponents:
        print(comp.get("SUMMARY"))

    # Get vobject object (a copy)
    vobj = event.get_vobject_instance()

Modifying Data
~~~~~~~~~~~~~~

To edit an object, use context managers that "borrow" the object:

.. code-block:: python

    # Edit using icalendar
    with event.edit_icalendar_instance() as cal:
        for comp in cal.subcomponents:
            if comp.name == "VEVENT":
                comp["SUMMARY"] = "New summary"
    event.save()

    # Edit using vobject
    with event.edit_vobject_instance() as vobj:
        vobj.vevent.summary.value = "New summary"
    event.save()

While inside the ``with`` block, the object is exclusively borrowed.
Attempting to borrow a different representation will raise ``RuntimeError``.

Quick Access
~~~~~~~~~~~~

For simple read access, use the ``component`` property:

.. code-block:: python

    # Read properties
    summary = event.component["SUMMARY"]
    start = event.component.start

.. _howtos:sequence:

Saving and the SEQUENCE Property
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, :meth:`~caldav.calendarobjectresource.CalendarObjectResource.save`
treats every save as a new revision by the organizer: if the component has a
``SEQUENCE`` property, it is incremented before the object is sent to the
server (:rfc:`5545#section-3.8.7.4`).  An object without ``SEQUENCE`` is left
without one.  The same default applies to
:meth:`~caldav.collection.Calendar.add_event`,
:meth:`~caldav.collection.Calendar.add_todo`,
:meth:`~caldav.collection.Calendar.add_journal`,
:meth:`~caldav.collection.Calendar.add_object` and
:meth:`~caldav.collection.Calendar.save_with_invites`, so adding iCalendar data
that already carries ``SEQUENCE:3`` stores ``SEQUENCE:4``.

Pass ``increase_seqno=False`` when the data should be stored as it is:

.. code-block:: python

    # A cosmetic edit that should not count as a new revision
    with event.edit_icalendar_component() as comp:
        comp["DESCRIPTION"] = "Fixed a typo"
    event.save(increase_seqno=False)

    # Copying, restoring or syncing data from elsewhere
    cal.add_event(ical_data, increase_seqno=False)

**Sync, copy, backup-restore and migration tools should always pass**
``increase_seqno=False``.  Such a tool writes data it read somewhere else; it is
not revising the event.  With the default, every round of a two-way sync bumps
``SEQUENCE`` again, the two sides never converge, and attendees may be told
about a change that did not happen.

When a single recurrence is saved (see :ref:`tutorial:Modifying Events`), the
``SEQUENCE`` of that recurrence is incremented, not the one of the master
event.  Replying to an invitation (``accept_invite()`` and friends) never
increments ``SEQUENCE``; only the organizer revises an event.

The Server's Bytes
~~~~~~~~~~~~~~~~~~

``data``, ``wire_data`` and the parsed instances are caldav's normalised copy
of an object: incoming data goes through ``vcal.fix()``, and ``wire_data`` is
re-serialised after an edit.  To compare or copy what a server actually
stores, use
:attr:`~caldav.calendarobjectresource.CalendarObjectResource.raw_data` and
``save(raw_data=...)``:

.. code-block:: python

    source = source_cal.get_event_by_uid(uid).load()
    raw = source.raw_data          # bytes, as the server sent them

    ## a new object in the target calendar; its URL comes from the UID
    Event(parent=target_cal).save(raw_data=raw)
    ## or overwrite an object loaded from the target, with its If-Match
    target_cal.get_event_by_uid(uid).save(raw_data=raw)

``raw_data`` is a snapshot of the last read: editing the object does not change
it, a successful ``save()`` clears it (the server's bytes are only known after
the next load), and it is ``None`` for an object built locally or copied,
including the occurrences ``search(expand=True)`` returns.  An object a search
filtered or expanded in place keeps what the server sent, which after a
server-side expansion is the expanded text: ``load()`` before copying.
``save(raw_data=None)`` raises ``ValueError`` instead of saving something else.
After ``load()`` (a GET) it is the response body byte for byte.  From a
REPORT (``search()``, ``multiget()``, a ``load()`` that falls back to
multiget) it is the text of the ``calendar-data`` XML element, UTF-8
encoded: the XML parser has decoded entities such as ``&amp;`` and turned
CRLF into LF, so call ``load()`` first when the exact bytes matter.

``save(raw_data=...)`` sends the bytes without ``vcal.fix()``, re-serialising,
line ending changes, ``SEQUENCE`` bump or merging a recurrence into its master,
and they replace any local edit, even if the PUT fails.  The bytes must be
UTF-8.  ``If-Match`` / ``If-Schedule-Tag-Match``,
``no_overwrite`` and ``no_create`` apply as for any save.

Backing Up a Calendar
---------------------

Use :func:`caldav.get_calendar` (available since v2.0) to fetch all objects
from a specific calendar and write them to disk:

.. code-block:: python

    import pathlib
    from caldav import get_calendar

    backup_dir = pathlib.Path("backup")
    backup_dir.mkdir(exist_ok=True)

    with get_calendar(calendar_name="Work") as cal:
        for obj in cal.search():
            uid = obj.icalendar_instance.subcomponents[0]["UID"]
            (backup_dir / f"{uid}.ics").write_text(obj.data)

To restore, iterate over the saved ``.ics`` files and call
``cal.add_event(data, increase_seqno=False)`` (or ``add_todo()``/``add_journal()``
as appropriate).  Without ``increase_seqno=False`` the restored objects get
their ``SEQUENCE`` bumped, see :ref:`howtos:sequence`.

For more on server-specific connection details and known incompatibilities,
see :ref:`about:Compatibility` and :ref:`about:Some notes on CalDAV URLs`.
