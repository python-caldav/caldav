.. python-caldav documentation master file, created by
   sphinx-quickstart on Thu Jun  3 10:47:52 2010.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Documentation: caldav |release|
======================================

Contents
--------

.. toctree::
   :maxdepth: 1

   caldav/davclient
   caldav/objects


Quickstart
----------

.. code-block:: python

  from datetime import datetime
  import caldav
  from caldav.elements import dav, cdav
  
  # Caldav url
  url = "https://user:pass@hostname/caldav.php/"
  
  vcal = """BEGIN:VCALENDAR
  VERSION:2.0
  PRODID:-//Example Corp.//CalDAV Client//EN
  BEGIN:VEVENT
  UID:1234567890
  DTSTAMP:20100510T182145Z
  DTSTART:20100512T170000Z
  DTEND:20100512T180000Z
  SUMMARY:This is an event
  END:VEVENT
  END:VCALENDAR
  """
  
  client = caldav.DAVClient(url)
  principal = caldav.Principal(client)
  calendars = principal.calendars()
  if len(calendars) > 0:
      calendar = calendars[0]
      print "Using calendar", calendar
  
      print "Renaming"
      calendar.set_properties([dav.DisplayName("Test calendar"),])
      print calendar.get_properties([dav.DisplayName(),])
  
      event = calendar.add_event(vcal)
      print "Event", event, "created"
  
      print "Looking for events after 2010-05-01"
      results = calendar.date_search(datetime(2010, 5, 1))
      for event in results:
          print "Found", event


Unit testing
------------

To start the unit tests, run:

.. code-block:: bash

  $ python setup.py nosetests


Documentation
-------------

To build the documentation, run:

.. code-block:: bash

  $ python setup.py build_sphinx


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

