"""
JSCalendar ↔ iCalendar conversion utilities.

Public API:
    ical_to_jscal(ical_str, calendar_id=None) -> dict
    jscal_to_ical(jscal) -> str
"""

from caldav.jmap.convert.ical_to_jscal import ical_to_jscal
from caldav.jmap.convert.jscal_to_ical import jscal_to_ical

__all__ = ["ical_to_jscal", "jscal_to_ical"]
