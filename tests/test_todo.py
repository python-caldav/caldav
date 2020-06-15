from unittest import TestCase

from caldav.objects import Todo


# example from http://www.rfc-editor.org/rfc/rfc5545.txt
VTODO = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
UID:20070313T123432Z-456553@example.com
DTSTAMP:20070313T123432Z
DUE;VALUE=DATE:20070501
SUMMARY:Submit Quebec Income Tax Return for 2006
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY,FINANCE
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""


## a todo without uid.  Should it be possible to store it at all?
VTODO_NO_UID = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Example Corp.//CalDAV Client//EN
BEGIN:VTODO
DTSTAMP:19980101T130000Z
DTSTART:19980415T133000Z
DUE:19980516T045959Z
SUMMARY:Get stuck with Netfix and forget about the tax income declaration
CLASS:CONFIDENTIAL
CATEGORIES:FAMILY
PRIORITY:1
END:VTODO
END:VCALENDAR"""


class TodoTestCase(TestCase):

    def test_it_sets_the_id(self):
        todo = Todo(data=VTODO)

        self.assertEqual(todo.id, "20070313T123432Z-456553@example.com")

    def test_it_prefers_the_id_of_the_vtodo(self):
        # Is this actually the expected behaviour?
        todo = Todo(data=VTODO, id="some-valid-id")

        self.assertEqual(todo.id, "20070313T123432Z-456553@example.com")
        
    def test_it_sets_the_id_to_none_if_the_vtodo_has_no_uid(self):
        todo = Todo(data=VTODO_NO_UID)

        self.assertEqual(todo.id, None)

    def test_it_sets_the_id_to_the_value_provided_if_the_vtodo_has_no_uid(self):
        todo = Todo(data=VTODO_NO_UID, id="some-valid-id")

        self.assertEqual(todo.id, "some-valid-id")
