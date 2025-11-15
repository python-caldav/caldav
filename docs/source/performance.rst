===========
Performance
===========

The current maintainer of the CalDAV library was born in an age where memory and CPU was limited resources.  CPU and memory comes cheaply today (read https://www.aardvark.co.nz/daily/2025/0611.shtml to see what I mean).  The CalDAV and iCalendar protocols weren't really written for lean computing in the first place.  If you need something that can run around on what used to be a bleeding edge supercomputer, you probably need to scrap those standards and write your own optimized calendaring standard and your own server and client for it - and this probably has to be done in C, not in Python.

Still, sometimes all the extra bloat I've added to the CalDAV library makes me cringe a bit.  If you have issues with performance, please reach out (see the :ref:`contact:contact` document).

Some thoughts:

* While CPU and memory comes cheaply today, latency is often a problem.  Creating server requests and particularly initiating TCP connections are typically costly.  There are a number of places in the code where it may be possible to reduce the number of requests.  As of 2.x, consider reading the top of the CHANGELOG - utilizing the niquests rather than requests library may possibly make the server communication more snappy.
* In the early days almost all the necessary handling of icalendar data was done by accessing it as ``event.data``.  This may be the most efficient - but the ``vobject`` was also utilized.  Due to popular demand, plus the fact that ``vobject`` was not mainained for a while, ``icalendar`` took over.  I can imagine it does takes some CPU to convert the data between ical strings and instances.  This is done every time the data is accessed in a different format.  For performance reasons, I was initially not very happy to use the icalendar library for doing simple things like fetching the UID from an event - but I've come to think that this is necessary.  Now the problem is that every here and there there may still be some old code accessing ``event.data`` rather than ``event.icalendar_instance``.  This probably causes the burning of quite a lot of CPU cycles!
