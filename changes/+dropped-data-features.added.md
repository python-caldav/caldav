Compatibility features for data a server drops without saying so, found on Ox by the conformance suite of calendaring, each with a probe in caldav-server-tester (https://github.com/python-caldav/caldav-server-tester/issues/40):

- `save-load.icalendar.x-property`: an X- property is kept, in an event and in a task (Ox drops it from a task).
- `save-load.icalendar.unknown-property`: a property RFC 5545 does not define, ESTIMATED-DURATION in the probe, is kept.
- `save-load.todo.attendee`: a task with an ATTENDEE is stored (Ox answers 201, then 404: broken).
- `save-load.todo.completed-without-status`: a task with COMPLETED but no STATUS keeps its COMPLETED.
