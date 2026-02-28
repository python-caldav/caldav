"""
JMAP capability URN constants.

All JMAP capability strings are defined here so they are never duplicated
across the package. Every other module should import from this file.
"""

#: Core JMAP capability (RFC 8620) — required in every ``using`` declaration.
CORE_CAPABILITY = "urn:ietf:params:jmap:core"

#: JMAP Calendars capability (JMAP Calendars specification).
CALENDAR_CAPABILITY = "urn:ietf:params:jmap:calendars"

#: JMAP Tasks capability (JMAP Tasks specification).
TASK_CAPABILITY = "urn:ietf:params:jmap:tasks"
