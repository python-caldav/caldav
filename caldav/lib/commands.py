#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from lxml import etree
import uuid

from caldav.lib.namespace import ns, nsmap
from caldav.lib import url


def children(client, parent, type = None):
    """
    List children, using a propfind (resourcetype) on the parent object,
    at depth = 1.
    TODO: There should be a better way.
    """
    c = []

    response = get_properties(client, parent, [ns("D", "resourcetype"),], 1)
    for path in response.keys():
        if path != parent.url.path:
            resource_type = response[path][ns("D", 'resourcetype')]
            if resource_type == type or type is None:
                c.append((url.make(parent.url, path), resource_type))

    return c

def get_properties(client, object, props = [], depth = 0):
    """
    Find the properies `props` of object `object` and its children at
    maximum `depth` levels. (0 means only `object`).
    """
    rc = {}

    body = ""
    # build the propfind request
    if len(props) > 0:
        root = etree.Element("propfind", nsmap = nsmap)
        prop = etree.SubElement(root, ns("D", "prop"))
        for p in props:
            prop.append(etree.Element(p))
        body = etree.tostring(root, encoding="utf-8", xml_declaration=True)

    response = client.propfind(object.url.path, body, depth)
    # All items should be in a <D:response> element
    for r in response.tree.findall(ns("D", "response")):
        href = r.find(ns("D", "href")).text
        rc[href] = {}
        for p in props:
            t = r.find(".//" + p)
            if t.text is None:
                val = t.find(".//*")
                if val is not None:
                    val = val.tag
                else:
                    val = None
            else:
                val = t.text
            rc[href][p] = val

    return rc


def set_properties(client, object, props = []):
    root = etree.Element(ns("D", "propertyupdate"), nsmap = nsmap)
    set = etree.SubElement(root, ns("D", "set"))
    prop = etree.SubElement(set, ns("D", "prop"))
    for property in props.keys():
        elt = etree.SubElement(prop, property)
        elt.text = props[property]
    q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    print q
    r = client.proppatch(object.url.path, q)
    print r, r.raw


def date_search(client, calendar, start, end = None):
    """
    Perform a time-interval search in the `calendar`.
    """
    rc = []

    dates = {"start": start}
    if end is not None:
        dates['end'] = end
    
    # build the request
    root = etree.Element(ns("C", "calendar-query"), nsmap = nsmap)
    prop = etree.SubElement(root, ns("D", "prop"))
    cdata = etree.SubElement(prop, ns("C", "calendar-data"))
    expand = etree.SubElement(cdata, ns("C", "expand"), **dates)
    filter = etree.SubElement(root, ns("C", "filter"))
    fcal = etree.SubElement(filter, ns("C", "comp-filter"), name = "VCALENDAR")
    fevt = etree.SubElement(fcal, ns("C", "comp-filter"), name = "VEVENT")
    etree.SubElement(fevt, ns("C", "time-range"), **dates)

    q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    response = client.report(calendar.url.path, q, 1)
    for r in response.tree.findall(".//" + ns("D", "response")):
        href = r.find(ns("D", "href")).text
        data = r.find(".//" + ns("C", "calendar-data")).text
        rc.append((url.make(calendar.url, href), data))

    return rc

def uid_search(client, calendar, uid):
    """
    Perform a uid search in the `calendar`.
    """
    root = etree.Element(ns("C", "calendar-query"), nsmap = nsmap)
    prop = etree.SubElement(root, ns("D", "prop"))
    cdata = etree.SubElement(prop, ns("C", "calendar-data"))
    filter = etree.SubElement(root, ns("C", "filter"))
    fcal = etree.SubElement(filter, ns("C", "comp-filter"), name = "VCALENDAR")
    fevt = etree.SubElement(fcal, ns("C", "comp-filter"), name = "VEVENT")
    fuid = etree.SubElement(fevt, ns("C", "prop-filter"), name = "UID")
    match = etree.SubElement(fuid, ns("C", "text-match"),
                             collation = "i; octet")
    match.text = uid

    q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    response = client.report(calendar.url.path, q, 1)
    r = response.tree.find(".//" + ns("D", "response"))
    href = r.find(ns("D", "href")).text
    data = r.find(".//" + ns("C", "calendar-data")).text
    return (url.make(calendar.url, href), data)

def create_calendar(client, parent, name, id = None):
    """
    Create a new calendar with display name `name` in `parent`.
    """
    path = None
    if id is None:
        id = str(uuid.uuid1())

    root = etree.Element(ns("D", "mkcol"), nsmap = nsmap)
    set = etree.SubElement(root, ns("D", "set"))
    prop = etree.SubElement(set, ns("D", "prop"))
    type = etree.SubElement(prop, ns("D", "resourcetype"))
    coll = etree.SubElement(type, ns("D", "collection"))
    calc = etree.SubElement(coll, ns("C", "calendar-collection"))
    dname = etree.SubElement(prop, ns("D", "displayname"))
    dname.text = name

    q = etree.tostring(root, encoding="utf-8", xml_declaration=True)
    path = url.join(parent.url.path, id)

    r = client.mkcol(path, q)
    if r.status == 201:
        path = url.make(parent.url, path)

    return (id, path)

def create_event(client, calendar, data, id = None):
    path = None
    if id is None:
        id = str(uuid.uuid1())

    path = url.join(calendar.url.path, id + ".ics")
    r = client.put(path, data)
    if r.status == 201:
        path = url.make(calendar.url, path)

    return (id, path)

def delete(client, object):
    path = object.url.path
    r = client.delete(path)

    return r.status == 204
