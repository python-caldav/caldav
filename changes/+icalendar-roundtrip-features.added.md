Compatibility features for iCalendar data a server does not keep, found by the conformance suite of calendaring (https://github.com/pycalendar/calendaring), each with a probe in caldav-server-tester:

- `save-load.icalendar.participant`: an RFC 9073 PARTICIPANT inside a VEVENT is stored.  CCS and Bedework 3 refuse the event with 403, robur with 400, GMX and Ox with 500 (https://github.com/python-caldav/caldav-server-tester/issues/38).
- `save-load.icalendar.vtimezone`: the VTIMEZONE sent with an object comes back with it.  CCS returns the TZID without it (https://github.com/python-caldav/caldav-server-tester/issues/39).
