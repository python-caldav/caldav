#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import copy
import urlparse
import vobject
import StringIO

from caldav.lib import vcal
from caldav.lib.namespace import ns
from caldav.lib import url
from caldav.lib import commands

class DAVObject(object):
    """
    Base class for all DAV objects.
    """
    id = None
    url = None
    client = None
    parent = None
    name = None

    def __init__(self, client, url = None, parent = None, name = None, id = None):
        """
        Default constructor. 

        Parameters:
         * client: A DAVClient instance
         * url: The url for this object
         * parent: The parent object
         * name: A displayname
         * id: The resource id (UID for an Event)
        """

        self.client = client
        self.parent = parent
        self.name = name
        self.id = id
        if url is not None:
            self.url = urlparse.urlparse(url)
 
    def get_properties(self, props):
        """
        Get properties (PROPFIND) for this object.

        Parameters:
         * props = [ns("C", "propname"), ...]

        Returns:
         * {ns("C", "propname"): value, ...}
        """
        p = commands.get_properties(self.client, self, props)
        return p[self.url.path]

    def set_properties(self, props):
        """
        Set properties (PROPPATCH) for this object.

        Parameters:
         * props = {ns("C", "propname"): value, ...}

        Returns: 
         * self
        """
        commands.set_properties(self.client, self, props)
        return self
    
    def save(self):
        raise Exception("Must be defined in subclasses")

    def delete(self):
        """
        Delete the object.
        """
        if self.url is not None:
            commands.delete(self.client, self)



class Principal(DAVObject):
    """
    This class represents a DAV Principal. It doesn't do much, except play 
    the role of the parent to all calendar collections.

    Available DAV properties:
     * ns("D", "displayname")
    """
    def __init__(self, client, url):
        """
        This object has a specific constructor, because its url is mandatory.
        """
        self.client = client
        self.url = urlparse.urlparse(url)

    def calendars(self):
        """
        List all calendar collections in this principal.

        Returns:
         * [Calendar(), ...]
        """
        c = []

        data = commands.children(self.client, self, ns("D", "collection"))
        for c_url, c_type in data:
            c.append(Calendar(self.client, c_url, parent = self))

        return c


class Calendar(DAVObject):
    """
    The `Calendar` object is used to represent a calendar collection.

    Available CalDAV properties:
     * ns("C", "calendar-description")
     * ns("C", "calendar-timezone")
     * ns("C", "supported-calendar-component-set")
     * ns("C", "supported-calendar-data")
     * ns("C", "max-resource-size")
     * ns("C", "min-date-time")
     * ns("C", "max-date-time")
     * ns("C", "max-instances")
     * ns("C", "max-attendees-per-instance")

    Available DAV properties:
     * ns("D", "displayname")
    
    Refer to the RFC for details: http://www.ietf.org/rfc/rfc4791.txt
    """
    def save(self):
        """
        The save method for a calendar is only used to create it, for now.
        We know we have to create it when we don't have a url.

        Returns:
         * self
        """
        if self.url is None:
            (id, path) = commands.create_calendar(self.client, self.parent, 
                                                  self.name, self.id)
            self.id = id
            if path is not None:
                self.url = urlparse.urlparse(path)
        return self

    def date_search(self, start, end = None):
        """
        Search events by date in the calendar. Recurring events are expanded 
        if they have an occurence during the specified time frame.

        Parameters:
         * start = "20100528T124500Z", a vCal-formatted string describing 
           a date-time.
         * end = "20100528T124500Z", same as above.

        Returns:
         * [Event(), ...]
        """
        e = []

        data = commands.date_search(self.client, self, start, end)
        for e_url, e_data in data:
            e.append(Event(self.client, url = e_url, data = e_data, 
                           parent = self))

        return e

    def event(self, uid):
        """
        Get one event from the calendar.

        Parameters:
         * uid: the event uid

        Returns:
         * Event() or None
        """
        (e_url, e_data) = commands.uid_search(self.client, self, uid)
        e = Event(self.client, url = e_url, data = e_data, parent = self)

        return e

    def events(self):
        """
        List all events from the calendar.

        Returns:
         * [Event(), ...]
        """
        e = []

        data = commands.children(self.client, self)
        for e_url, e_type in data:
            e.append(Event(self.client, e_url, parent = self))

        return e

    def __str__(self):
        return "Collection: %s" % url.make(self.url)


class Event(DAVObject):
    """
    The `Event` object is used to represent an event.
    """
    _instance = None
    _data = None

    def __init__(self, client, url = None, data = None, parent = None, id = None):
        """
        Event has an additional parameter for its constructor:
         * data = "...", vCal data for the event
        """
        DAVObject.__init__(self, client, url, parent, id)
        if data is not None:
            self.data = data

    def load(self):
        """
        Load the event from the caldav server.
        """
        r = self.client.request(self.url.path)
        self.data = vcal.fix(r.raw)
        return self

    def save(self):
        """
        Save the event, can be used for creation and update.

        Returns:
         * self
        """
        if self._instance is not None:
            (id, path) = commands.create_event(self.client, self.parent, 
                                               self._instance.serialize(), 
                                               self.id)
            self.id = id
            if path is not None:
                self.url = urlparse.urlparse(path)
        return self

    def __str__(self):
        return "Event: %s" % url.make(self.url)


    def set_data(self, data):
        self._data = vcal.fix(data)
        self._instance = vobject.readOne(StringIO.StringIO(self._data))
        return self
    def get_data(self):
        return self._data
    data = property(get_data, set_data, 
                    doc = "vCal representation of the event")

    def set_instance(self, inst):
        self._instance = inst
        self._data = inst.serialize()
        return self
    def get_instance(self):
        return self._instance
    instance = property(get_instance, set_instance, 
                        doc = "vobject instance of the event")


