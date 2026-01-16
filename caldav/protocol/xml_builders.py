"""
Pure functions for building CalDAV XML request bodies.

All functions in this module are pure - they take data in and return XML out,
with no side effects or I/O.
"""
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from lxml import etree

from caldav.elements import cdav
from caldav.elements import dav
from caldav.elements.base import BaseElement


def build_propfind_body(
    props: Optional[List[str]] = None,
    allprop: bool = False,
) -> bytes:
    """
    Build PROPFIND request body XML.

    Args:
        props: List of property names to retrieve. If None and allprop=False,
               returns minimal propfind.
        allprop: If True, request all properties.

    Returns:
        UTF-8 encoded XML bytes
    """
    if allprop:
        propfind = dav.Propfind() + dav.Allprop()
    elif props:
        prop_elements = []
        for prop_name in props:
            prop_element = _prop_name_to_element(prop_name)
            if prop_element is not None:
                prop_elements.append(prop_element)
        propfind = dav.Propfind() + (dav.Prop() + prop_elements)
    else:
        propfind = dav.Propfind() + dav.Prop()

    return etree.tostring(propfind.xmlelement(), encoding="utf-8", xml_declaration=True)


def build_proppatch_body(
    set_props: Optional[Dict[str, Any]] = None,
) -> bytes:
    """
    Build PROPPATCH request body for setting properties.

    Args:
        set_props: Properties to set (name -> value)

    Returns:
        UTF-8 encoded XML bytes
    """
    propertyupdate = dav.PropertyUpdate()

    if set_props:
        set_elements = []
        for name, value in set_props.items():
            prop_element = _prop_name_to_element(name, value)
            if prop_element is not None:
                set_elements.append(prop_element)
        if set_elements:
            set_element = dav.Set() + (dav.Prop() + set_elements)
            propertyupdate += set_element

    return etree.tostring(
        propertyupdate.xmlelement(), encoding="utf-8", xml_declaration=True
    )


def build_calendar_query_body(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    expand: bool = False,
    comp_filter: Optional[str] = None,
    event: bool = False,
    todo: bool = False,
    journal: bool = False,
    props: Optional[List[BaseElement]] = None,
    filters: Optional[List[BaseElement]] = None,
) -> Tuple[bytes, Optional[str]]:
    """
    Build calendar-query REPORT request body.

    This is the core CalDAV search operation for retrieving calendar objects
    matching specified criteria.

    Args:
        start: Start of time range filter
        end: End of time range filter
        expand: Whether to expand recurring events
        comp_filter: Component type filter name (VEVENT, VTODO, VJOURNAL)
        event: Include VEVENT components (sets comp_filter if not specified)
        todo: Include VTODO components (sets comp_filter if not specified)
        journal: Include VJOURNAL components (sets comp_filter if not specified)
        props: Additional CalDAV properties to include
        filters: Additional filters to apply

    Returns:
        Tuple of (UTF-8 encoded XML bytes, component type name or None)
    """
    # Build calendar-data element with optional expansion
    data = cdav.CalendarData()
    if expand:
        if not start or not end:
            from caldav.lib import error

            raise error.ReportError("can't expand without a date range")
        data += cdav.Expand(start, end)

    # Build props
    props_list: List[BaseElement] = [data]
    if props:
        props_list.extend(props)
    prop = dav.Prop() + props_list

    # Build VCALENDAR filter
    vcalendar = cdav.CompFilter("VCALENDAR")

    # Determine component filter from flags
    comp_type = comp_filter
    if not comp_type:
        if event:
            comp_type = "VEVENT"
        elif todo:
            comp_type = "VTODO"
        elif journal:
            comp_type = "VJOURNAL"

    # Build filter list
    filter_list: List[BaseElement] = []
    if filters:
        filter_list.extend(filters)

    # Add time range filter if specified
    if start or end:
        filter_list.append(cdav.TimeRange(start, end))

    # Build component filter
    if comp_type:
        comp_filter_elem = cdav.CompFilter(comp_type)
        if filter_list:
            comp_filter_elem += filter_list
        vcalendar += comp_filter_elem
    elif filter_list:
        vcalendar += filter_list

    # Build final query
    filter_elem = cdav.Filter() + vcalendar
    root = cdav.CalendarQuery() + [prop, filter_elem]

    return (
        etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True),
        comp_type,
    )


def build_calendar_multiget_body(
    hrefs: List[str],
    include_data: bool = True,
) -> bytes:
    """
    Build calendar-multiget REPORT request body.

    Used to retrieve multiple calendar objects by their URLs in a single request.

    Args:
        hrefs: List of calendar object URLs to retrieve
        include_data: Include calendar-data in response

    Returns:
        UTF-8 encoded XML bytes
    """
    elements: List[BaseElement] = []

    if include_data:
        prop = dav.Prop() + cdav.CalendarData()
        elements.append(prop)

    for href in hrefs:
        elements.append(dav.Href(href))

    multiget = cdav.CalendarMultiGet() + elements

    return etree.tostring(multiget.xmlelement(), encoding="utf-8", xml_declaration=True)


def build_sync_collection_body(
    sync_token: Optional[str] = None,
    props: Optional[List[str]] = None,
    sync_level: str = "1",
) -> bytes:
    """
    Build sync-collection REPORT request body.

    Used for efficient synchronization - only returns changed items since
    the given sync token.

    Args:
        sync_token: Previous sync token (empty string for initial sync)
        props: Property names to include in response
        sync_level: Sync level (usually "1")

    Returns:
        UTF-8 encoded XML bytes
    """
    elements: List[BaseElement] = []

    # Sync token (empty for initial sync)
    token_elem = dav.SyncToken(sync_token or "")
    elements.append(token_elem)

    # Sync level
    level_elem = dav.SyncLevel(sync_level)
    elements.append(level_elem)

    # Properties to return
    if props:
        prop_elements = []
        for prop_name in props:
            prop_element = _prop_name_to_element(prop_name)
            if prop_element is not None:
                prop_elements.append(prop_element)
        if prop_elements:
            elements.append(dav.Prop() + prop_elements)
    else:
        # Default: return etag and calendar-data
        elements.append(dav.Prop() + [dav.GetEtag(), cdav.CalendarData()])

    sync_collection = dav.SyncCollection() + elements

    return etree.tostring(
        sync_collection.xmlelement(), encoding="utf-8", xml_declaration=True
    )


def build_freebusy_query_body(
    start: datetime,
    end: datetime,
) -> bytes:
    """
    Build free-busy-query REPORT request body.

    Args:
        start: Start of free-busy period
        end: End of free-busy period

    Returns:
        UTF-8 encoded XML bytes
    """
    root = cdav.FreeBusyQuery() + [cdav.TimeRange(start, end)]

    return etree.tostring(root.xmlelement(), encoding="utf-8", xml_declaration=True)


def build_mkcalendar_body(
    displayname: Optional[str] = None,
    description: Optional[str] = None,
    timezone: Optional[str] = None,
    supported_components: Optional[List[str]] = None,
) -> bytes:
    """
    Build MKCALENDAR request body.

    Args:
        displayname: Calendar display name
        description: Calendar description
        timezone: VTIMEZONE component data
        supported_components: List of supported component types (VEVENT, VTODO, etc.)

    Returns:
        UTF-8 encoded XML bytes
    """
    prop = dav.Prop()

    if displayname:
        prop += dav.DisplayName(displayname)

    if description:
        prop += cdav.CalendarDescription(description)

    if timezone:
        prop += cdav.CalendarTimeZone(timezone)

    if supported_components:
        sccs = cdav.SupportedCalendarComponentSet()
        for comp in supported_components:
            sccs += cdav.Comp(comp)
        prop += sccs

    # Add resource type
    prop += dav.ResourceType() + [dav.Collection(), cdav.Calendar()]

    set_elem = dav.Set() + prop
    mkcalendar = cdav.Mkcalendar() + set_elem

    return etree.tostring(
        mkcalendar.xmlelement(), encoding="utf-8", xml_declaration=True
    )


def build_mkcol_body(
    displayname: Optional[str] = None,
    resource_types: Optional[List[BaseElement]] = None,
) -> bytes:
    """
    Build MKCOL (extended) request body.

    Args:
        displayname: Collection display name
        resource_types: List of resource type elements

    Returns:
        UTF-8 encoded XML bytes
    """
    prop = dav.Prop()

    if displayname:
        prop += dav.DisplayName(displayname)

    if resource_types:
        rt = dav.ResourceType()
        for rt_elem in resource_types:
            rt += rt_elem
        prop += rt
    else:
        prop += dav.ResourceType() + dav.Collection()

    set_elem = dav.Set() + prop
    mkcol = dav.Mkcol() + set_elem

    return etree.tostring(mkcol.xmlelement(), encoding="utf-8", xml_declaration=True)


# Property name to element mapping


def _prop_name_to_element(
    name: str, value: Optional[Any] = None
) -> Optional[BaseElement]:
    """
    Convert property name string to element object.

    Args:
        name: Property name (case-insensitive)
        value: Optional value for valued elements

    Returns:
        BaseElement instance or None if unknown property
    """
    # DAV properties (only those that exist in dav.py)
    dav_props: Dict[str, Any] = {
        "displayname": dav.DisplayName,
        "resourcetype": dav.ResourceType,
        "getetag": dav.GetEtag,
        "current-user-principal": dav.CurrentUserPrincipal,
        "owner": dav.Owner,
        "sync-token": dav.SyncToken,
        "supported-report-set": dav.SupportedReportSet,
    }

    # CalDAV properties
    caldav_props: Dict[str, Any] = {
        "calendar-data": cdav.CalendarData,
        "calendar-home-set": cdav.CalendarHomeSet,
        "calendar-user-address-set": cdav.CalendarUserAddressSet,
        "calendar-user-type": cdav.CalendarUserType,
        "calendar-description": cdav.CalendarDescription,
        "calendar-timezone": cdav.CalendarTimeZone,
        "supported-calendar-component-set": cdav.SupportedCalendarComponentSet,
        "schedule-inbox-url": cdav.ScheduleInboxURL,
        "schedule-outbox-url": cdav.ScheduleOutboxURL,
    }

    name_lower = name.lower().replace("_", "-")

    # Check DAV properties
    if name_lower in dav_props:
        cls = dav_props[name_lower]
        if value is not None:
            try:
                return cls(value)
            except TypeError:
                return cls()
        return cls()

    # Check CalDAV properties
    if name_lower in caldav_props:
        cls = caldav_props[name_lower]
        if value is not None:
            try:
                return cls(value)
            except TypeError:
                return cls()
        return cls()

    return None


def _to_utc_date_string(ts: datetime) -> str:
    """
    Convert datetime to UTC date string for CalDAV.

    Args:
        ts: datetime object (may or may not have timezone)

    Returns:
        UTC date string in format YYYYMMDDTHHMMSSZ
    """
    from datetime import timezone

    utc_tz = timezone.utc

    if ts.tzinfo is None:
        # Assume local time, convert to UTC
        try:
            ts = ts.astimezone(utc_tz)
        except Exception:
            # For very old Python versions or edge cases
            import tzlocal

            ts = ts.replace(tzinfo=tzlocal.get_localzone())
            ts = ts.astimezone(utc_tz)
    else:
        ts = ts.astimezone(utc_tz)

    return ts.strftime("%Y%m%dT%H%M%SZ")
