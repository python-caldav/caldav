====
JMAP
====

JMAP (:rfc:`8620`, JMAP Core, plus the JMAP Calendars protocol using
:rfc:`8984` JSCalendar) support moved out of this library into the standalone
`calendaring-jmap <https://pypi.org/project/calendaring-jmap/>`_ package.
``caldav.jmap`` is now a thin wrapper around it, so the ``from caldav.jmap
import get_jmap_client`` usage you may already have keeps working - it emits
a ``DeprecationWarning`` and will be removed in a future release.  Import
from ``calendaring_jmap`` directly in new code.

calendaring-jmap is an optional dependency; ``caldav.jmap`` raises an
``ImportError`` without it.  Install it with:

.. code-block:: shell

   pip install caldav[jmap]

The extra brings dependencies caldav itself does not have: calendaring-jmap
requires ``icalendar>=7.3.0``, which is a higher floor than caldav's own
``icalendar>6.0.0``, and it requires both ``niquests`` and ``requests``, so
``requests`` arrives even in an environment built to avoid it (see
:doc:`http-libraries`).

.. note::

   calendaring-jmap is licensed **AGPL-3.0-or-later**, while caldav itself
   is ``GPL-3.0-or-later OR Apache-2.0``.  Pulling in the ``jmap`` extra
   therefore brings the AGPL network-copyleft obligation into your
   dependency tree, even though the import path is unchanged.  This does
   not affect caldav installed without the extra.

For the full client API, calendar/event/task operations, and conversion
details, see `calendaring-jmap's own documentation
<https://calendaring-jmap.readthedocs.io/en/stable/>`_.

Quick Start
===========

.. code-block:: python

    from caldav.jmap import get_jmap_client

    with get_jmap_client(
        url="https://jmap.example.com/.well-known/jmap",
        username="alice",
        password="secret",
    ) as client:
        calendars = client.get_calendars()
        for cal in calendars:
            print(cal.name)

Configuration
=============

Unlike calendaring-jmap used standalone (which reads ``JMAP_*`` env vars and
its own config file), :func:`~caldav.jmap.get_jmap_client` reads
configuration from the same sources as :func:`caldav.get_davclient`: explicit
keyword arguments, then ``CALDAV_URL`` / ``CALDAV_USERNAME`` /
``CALDAV_PASSWORD`` environment variables, then a config file, the same file
CalDAV settings live in, so both protocols can share one config. See
:doc:`configfile` for file locations and section options.

.. code-block:: python

    client = get_jmap_client()   # reads env vars or config file

Error Handling
==============

JMAP errors raised through ``caldav.jmap`` (:class:`~caldav.jmap.JMAPError`
and subclasses) are also :class:`caldav.lib.error.DAVError` subclasses, so
existing ``except DAVError`` handling around CalDAV code catches JMAP errors
too:

.. code-block:: python

    from caldav.lib.error import DAVError

    try:
        client.get_calendars()
    except DAVError as e:
        print(f"JMAP request failed: {e}")

API Reference
=============

* :doc:`caldav/jmap_wrapper`: the wrapper's own surface (:func:`~caldav.jmap.get_jmap_client`,
  :func:`~caldav.jmap.get_async_jmap_client`, and the ``DAVError``-compatible error classes)
* `calendaring-jmap reference docs <https://calendaring-jmap.readthedocs.io/en/stable/>`_:
  full ``JMAPClient``/``AsyncJMAPClient`` method reference, ``JMAPCalendar``, ``JMAPCalendarObject``
