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

.. todo::

   * Make a how-to on how to create a local backup and syncing it.  (procrastinated until the ``get_calendar`` function is completed)
   * Make how-tos on each known calendar server and/or service provider - including known incompatibilities.  Some information in the `about.rst`, should be moved here
   * Particularly Google.

   See also https://github.com/python-caldav/caldav/issues/513
