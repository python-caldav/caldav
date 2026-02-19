"""
JMAP capability URN constants (RFC 8620, JMAP Calendars spec, RFC 9553).

All JMAP capability strings are defined here so they are never duplicated
across the package. Every other module should import from this file.
"""

#: Core JMAP capability — required in every ``using`` declaration.
CORE_CAPABILITY = "urn:ietf:params:jmap:core"

#: RFC 8620 JMAP Calendars capability.
CALENDAR_CAPABILITY = "urn:ietf:params:jmap:calendars"

#: RFC 9553 JMAP Tasks capability.
TASK_CAPABILITY = "urn:ietf:params:jmap:tasks"
