#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from lxml import etree
import uuid

from caldav.objects import Principal, Calendar, Event
from caldav.utils.namespace import ns, nsmap


def children(client, object, type = None):
    c = []
    response = properties(client, object, 
                          [("D", "resourcetype"),], 1)
    for path in response.keys():
        print path, object.url.path
        if path != object.url.path:
            rtype = response[path][ns("D", 'resourcetype')]
            if rtype is not None and rtype == ns("D", "collection"):
                cls = Calendar
            else:
                cls = Event

            if rtype == type or type is None:
                c.append(cls(client, url = object.geturl(path), 
                             parent = object))
    return c

def properties(client, object, props = [], depth = 0):
    rc = {}
    body = ""
    if len(props) > 0:
        root = etree.Element("propfind", nsmap = nsmap)
        prop = etree.SubElement(root, ns("D", "prop"))
        for p in props:
            prop.append(etree.Element(ns(*p)))
        body = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    response = client.propfind(object.url.path, body, depth)
    for r in response.tree.findall(ns("D", "response")):
        href = r.find(ns("D", "href")).text
        rc[href] = {}
        for p in props:
            t = r.find(".//" + ns(*p))
            if t.text is None:
                val = t.find(".//*")
                if val is not None:
                    val = val.tag
                else:
                    val = None
            else:
                val = t.text
            rc[href][ns(*p)] = val
    return rc

def date_search(client, object, start, end = None):
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
    response = client.report(object.url.path, q, 1)
    for r in response.tree.findall(".//" + ns("D", "response")):
        href = r.find(ns("D", "href")).text
        data = r.find(".//" + ns("C", "calendar-data")).text
        rc.append(Event(client, url = object.geturl(href), data = data, parent = object))

    return rc

def create_calendar(client, parent, name):
    root = etree.Element(ns("D", "mkcol"), nsmap = nsmap)
    set = etree.SubElement(root, ns("D", "set"))
    prop = etree.SubElement(set, ns("D", "prop"))
    type = etree.SubElement(prop, ns("D", "resourcetype"))
    coll = etree.SubElement(prop, ns("D", "collection"))
    calc = etree.SubElement(coll, ns("C", "calendar-collection"))
    dname = etree.SubElement(prop, ns("D", "displayname"))
    dname.text = name

    q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    id = str(uuid.uuid1())
    path = parent.url.path + id

    r = client.mkcol(path, q)
    if r.status == 201:
        url = parent.geturl(path)
    else:
        url = None

    return url

def create_event(client, parent, data):
    id = str(uuid.uuid1())
    path = parent.url.path + "/" + id + ".ics"
    print path
    r = client.put(path, data)
    if r.status == 201:
        url = parent.geturl(path)
    else:
        url = None

    return url
