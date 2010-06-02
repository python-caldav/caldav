#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from lxml import etree

from objects import Principal, Collection, Event
from davclient import DAVClient
from utils.namespace import ns, nsmap

class CalDAV(DAVClient):
    def load(self, object):
        object.load(self)

    def children(self, object, type = None):
        c = []
        response = self.properties(object, 
                                   [("D", "displayname"), ("D", "resourcetype")], 1)
        for path in response.keys():
            if path != object.url.path:
                rtype = response[path][ns("D", 'resourcetype')]
                if rtype is not None and rtype == ns("D", "collection"):
                    cls = Collection
                else:
                    cls = Event

                if rtype == type or type is None:
                    c.append(cls(object.geturl(path)))
        return c

    def properties(self, object, props = {}, depth = 0):
        rc = {}
        body = ""
        if len(props) > 0:
            root = etree.Element("propfind", nsmap = nsmap)
            prop = etree.SubElement(root, ns("D", "prop"))
            for p in props:
                prop.append(etree.Element(ns(*p)))
            body = etree.tostring(root, encoding="utf-8", xml_declaration=True)
        response = self.propfind(object.url.path, body, depth)
        for r in response.tree.findall(ns("D", "response")):
            href = r.find(ns("D", "href")).text
            rc[href] = {}
            for p in props:
                t = r.find(".//" + ns(*p))
                if t.text is None:
                    val = t.find(".//*").tag
                else:
                    val = t.text
                rc[href][ns(*p)] = val
        return rc

    def date_search(self, object, start, end = None):
        rc = []

        dates = {"start": start}
        if end is not None:
            dates['end'] = end
        
        root = etree.Element(ns("C", "calendar-query"), nsmap = nsmap)
        prop = etree.SubElement(root, ns("D", "prop"))
        cdata = etree.SubElement(prop, ns("C", "calendar-data"))
        expand = etree.SubElement(cdata, ns("C", "expand"), **dates)
        filter = etree.SubElement(root, ns("C", "filter"))
        fcal = etree.SubElement(filter, ns("C", "comp-filter"), name = "VCALENDAR")
        fevt = etree.SubElement(fcal, ns("C", "comp-filter"), name = "VEVENT")
        etree.SubElement(fevt, ns("C", "time-range"), **dates)

        q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
        print q
        response = self.report(object.url.path, q, 1)
        for r in response.tree.findall(".//" + ns("D", "response")):
            href = r.find(ns("D", "href")).text
            data = r.find(".//" + ns("C", "calendar-data")).text
            rc.append(Event(object.geturl(href), data))

        return rc


if __name__ == "__main__":
    p = "http://sogo1:sogo1@sogo-demo.inverse.ca:80/SOGo/dav/sogo1/Calendar/"
    client = CalDAV(p)
    pri = Principal(p)
    #print client.properties(pri, [("D", "displayname"), ("D", "resourcetype")])
    collections = client.children(pri, "{DAV:}collection")
    print "Collections: ", collections

    for collection in collections:
        events = client.date_search(collection, "20100601T000000Z", "20100602T000000Z")
        for event in events:
            if event.instance.vevent.rruleset is not None:
                print event.instance.vevent.dtstart, event.instance.vevent.rruleset._rrule[0]
            else:
                print event.instance.vevent.dtstart, event.instance.vevent.rruleset
