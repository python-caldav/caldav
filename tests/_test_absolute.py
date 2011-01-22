# encoding: utf-8

import datetime

import caldav


class TestRadicale(object):

    SUMMARIES = set(('Godspeed You! Black Emperor at '
                     'Cirque Royal / Koninklijk Circus',
                     'Standard - GBA'))
    DTSTART = set((datetime.datetime(2011, 3, 4, 20, 0),
                   datetime.datetime(2011, 1, 15, 20, 0)))

    def setup(self):
        URL = 'http://localhost:8080/nicoe/perso/'
        self.client = caldav.DAVClient(URL)
        self.calendar = caldav.objects.Calendar(self.client, URL)

    def test_eventslist(self):
        events = self.calendar.events()
        assert len(events) == 2

        summaries, dtstart = set(), set()
        for event in events:
            event.load()
            vobj = event.instance
            summaries.add(vobj.vevent.summary.value)
            dtstart.add(vobj.vevent.dtstart.value)

        assert summaries == self.SUMMARIES
        assert dtstart == self.DTSTART


class TestTryton(object):

    def setup(self):
        URL = 'http://admin:admin@localhost:9080/caldav/Calendars/Test'
        self.client = caldav.DAVClient(URL)
        self.calendar = caldav.objects.Calendar(self.client, URL)

    def test_eventslist(self):
        events = self.calendar.events()
        assert len(events) == 1
