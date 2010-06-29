#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from lxml import etree
import uuid

from caldav.lib.namespace import ns, nsmap
from caldav.lib import url
from caldav.lib import error
from caldav.elements import dav, cdav


def children(client, parent, type = None):
    """
    List children, using a propfind (resourcetype) on the parent object,
    at depth = 1.
    TODO: There should be a better way.
    """
    c = []

    response = get_properties(client, parent, [dav.ResourceType(),], 1)
    for path in response.keys():
        if path != parent.url.path:
            resource_type = response[path][dav.ResourceType.tag]
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
        prop = dav.Prop() + props
        root = dav.Propfind() + prop

        body = etree.tostring(root.xmlelement(), encoding="utf-8", 
                              xml_declaration=True)

    response = client.propfind(object.url.path, body, depth)
    # All items should be in a <D:response> element
    for r in response.tree.findall(dav.Response.tag):
        href = r.find(dav.Href.tag).text
        rc[href] = {}
        for p in props:
            t = r.find(".//" + p.tag)
            if t.text is None:
                val = t.find(".//*")
                if val is not None:
                    val = val.tag
                else:
                    val = None
            else:
                val = t.text
            rc[href][p.tag] = val

    return rc


def set_properties(client, object, props = []):
    prop = dav.Prop() + props
    set = dav.Set() + prop
    root = dav.PropertyUpdate() + set

    q = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)
    r = client.proppatch(object.url.path, q)

    statuses = r.tree.findall(".//" + dav.Status.tag)
    for s in statuses:
        if not s.text.endswith("200 OK"):
            raise error.PropsetError(r.raw)


def date_search(client, calendar, start, end = None):
    """
    Perform a time-interval search in the `calendar`.
    """
    rc = []

    # build the request
    expand = cdav.Expand(start, end)
    data = cdav.CalendarData() + expand
    prop = dav.Prop() + data

    range = cdav.TimeRange(start, end)
    vevent = cdav.CompFilter("VEVENT") + range
    vcal = cdav.CompFilter("VCALENDAR") + vevent
    filter = cdav.Filter() + vcal

    root = cdav.CalendarQuery() + [prop, filter]

    q = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)
    response = client.report(calendar.url.path, q, 1)
    for r in response.tree.findall(".//" + dav.Response.tag):
        status = r.find(".//" + dav.Status.tag)
        if status.text.endswith("200 OK"):
            href = r.find(dav.Href.tag).text
            data = r.find(".//" + cdav.CalendarData.tag).text
            rc.append((url.make(calendar.url, href), data))
        else:
            raise error.ReportError(r.raw)

    return rc

def uid_search(client, calendar, uid):
    """
    Perform a uid search in the `calendar`.
    """
    data = cdav.CalendarData()
    prop = dav.Prop() + data

    match = cdav.TextMatch(uid)
    propf = cdav.PropFilter("UID") + match
    vevent = cdav.CompFilter("VEVENT") + propf
    vcal = cdav.CompFilter("VCALENDAR") + vevent
    filter = cdav.Filter() + vcal

    root = cdav.CalendarQuery() + [prop, filter]

    q = etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)
    response = client.report(calendar.url.path, q, 1)
    r = response.tree.find(".//" + dav.Response.tag)
    if r is not None:
        href = r.find(".//" + dav.Href.tag).text
        data = r.find(".//" + cdav.CalendarData.tag).text
        info = (url.make(calendar.url, href), data)
    else:
        raise error.NotFoundError(response.raw)

    return info

def create_calendar(client, parent, name, id = None):
    """
    Create a new calendar with display name `name` in `parent`.
    """
    path = None
    if id is None:
        id = str(uuid.uuid1())

    name = dav.DisplayName(name)
    cal = cdav.CalendarCollection()
    coll = dav.Collection() + cal
    type = dav.ResourceType() + coll
    
    prop = dav.Prop() + [type, name]
    set = dav.Set() + prop

    mkcol = dav.Mkcol() + set

    q = etree.tostring(mkcol.xmlelement(), encoding="utf-8", xml_declaration=True)
    path = url.join(parent.url.path, id)

    r = client.mkcol(path, q)
    if r.status == 201:
        path = url.make(parent.url, path)
    else:
        raise error.MkcolError(r.raw)

    return (id, path)

def create_event(client, calendar, data, id = None):
    path = None
    if id is None:
        id = str(uuid.uuid1())

    path = url.join(calendar.url.path, id + ".ics")
    r = client.put(path, data, {"Content-Type": "text/calendar; charset=\"utf-8\""})
    if r.status == 204 or r.status == 201:
        path = url.make(calendar.url, path)
    else:
        raise error.PutError(r.raw)

    return (id, path)

def delete(client, object):
    path = object.url.path
    r = client.delete(path)

    #TODO: find out why we get 404
    if r.status != 204 and r.status != 404:
        raise error.DeleteError(r.raw)
