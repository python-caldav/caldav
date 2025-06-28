==================
Config file format
==================


The :class:`davclient.get_davclient` method (and perhaps in 2.1, also ``davclient.get_calendar``) can read from a config file.  It will look for it in the following locations:

* ``$HOME/.config/caldav/calendar.conf``
* ``$HOME/.config/caldav/calendar.yaml``
* ``$HOME/.config/caldav/calendar.json``
* ``$HOME/.config/calendar.conf``
* ``/etc/calendar.conf``

The config file has to be valid json or yaml (support for toml and Apple pkl may be considered).

The config file is expected to be divided in sections, where each section can describe locations and credentials to a CalDAV server, a CalDAV calendar or a collection of calendars/servers.  As of version 2.0, only the first is supported.

A config section can be given either through parameters to :class:`caldav.davclient.get_davclient` or by enviornment variable ``CALDAV_CONFIG_SECTION``.  If no section is given, the ``default`` section is used.

Connection parameters
=====================

The section should contain configuration keys and values.  All configuration keys starting with ``caldav_`` is considered to be connection parameters and is passed to the DAVClient object.  Typically,  ``caldav_url``, ``caldav_username`` and ``caldav_password`` should be passed.

Calendar parameters
===================

Not implemented yet.

Probably in version 2.1 or version 2.2, ``calendar_name``, ``calendar_id`` and ``calendar_url`` can be used to specify a calendar.

Inheritance and collections
===========================

A section may ``inherit`` another section.  This may typically be used if having several sections in the config file corresponding to the same server/user but different calendars, or several sections corresponding to the same calendar server, but different users.

If a section ``contains`` different other sections, it's efficiently a collection of calendars.  This is not relevant for 2.0 though.

Simple example
==============

.. code-block:: yaml

   ---
   default:
       caldav_url: http://caldav.example.com/dav/
       caldav_user: tor
       caldav_pass: hunter2
