==================
Config file format
==================

The :func:`caldav.davclient.get_davclient`, :func:`caldav.davclient.get_calendar`, and
:func:`caldav.davclient.get_calendars` functions read connection parameters from a config
file.  The file is searched in the following locations (first match wins):

* ``$HOME/.config/caldav/calendar.conf``
* ``$HOME/.config/caldav/calendar.yaml``
* ``$HOME/.config/caldav/calendar.json``
* ``$HOME/.config/calendar.conf``
* ``/etc/caldav/calendar.conf``
* ``/etc/calendar.conf``

The config file must be valid JSON or YAML.  The path can also be given
explicitly via the ``CALDAV_CONFIG_FILE`` environment variable.

Sections
========

The file is divided into named sections.  Each section contains key/value
pairs describing how to connect to a CalDAV server and optionally which
calendar to select.  The section to use is chosen as follows (first match
wins):

1. The ``config_section`` parameter passed to :func:`~caldav.davclient.get_davclient` /
   :func:`~caldav.davclient.get_calendars`.
2. The ``CALDAV_CONFIG_SECTION`` environment variable.
3. The ``default`` section.

Connection parameters
=====================

All keys starting with ``caldav_`` are connection parameters passed to the
:class:`~caldav.davclient.DAVClient` constructor after stripping the prefix.
The most common ones are:

.. list-table::
   :header-rows: 1

   * - Config key
     - DAVClient parameter
     - Notes
   * - ``caldav_url``
     - ``url``
     - CalDAV server URL
   * - ``caldav_username`` or ``caldav_user``
     - ``username``
     - Login name
   * - ``caldav_password`` or ``caldav_pass``
     - ``password``
     - Login password
   * - ``caldav_proxy``
     - ``proxy``
     - HTTP/HTTPS proxy URL
   * - ``caldav_timeout``
     - ``timeout``
     - Request timeout in seconds
   * - ``caldav_ssl_verify_cert``
     - ``ssl_verify_cert``
     - ``false`` to skip TLS verification

The special ``features`` key (not prefixed with ``caldav_``) names a
server-compatibility profile — e.g. ``xandikos``, ``radicale``, ``baikal``.
See :mod:`caldav.compatibility_hints` for the full list of known profiles.

Environment variable expansion
-------------------------------

Values may reference environment variables using ``${VAR}`` or
``${VAR:-default}`` syntax:

.. code-block:: yaml

    default:
        caldav_url: https://caldav.example.com/
        caldav_username: ${CALDAV_USER:-alice}
        caldav_password: ${CALDAV_PASSWORD}

Calendar parameters
===================

:func:`~caldav.davclient.get_calendar` and :func:`~caldav.davclient.get_calendars` accept
``calendar_name`` and ``calendar_url`` to select a specific calendar.  These
can also be set in a config section so that a named section always refers to
one particular calendar:

.. code-block:: yaml

    work_inbox:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret
        calendar_name: Inbox

    work_team:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret
        calendar_url: https://caldav.example.com/cal/shared/

Calling ``get_calendars(config_section="work_inbox")`` will return only the
calendar named ``Inbox`` on that server.

Section inheritance
===================

A section may declare ``inherits: <other_section>`` to copy all values from
another section and then override specific keys.  This is useful when several
sections share the same server or credentials:

.. code-block:: yaml

    base_work:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret

    work_inbox:
        inherits: base_work
        calendar_name: Inbox

    work_tasks:
        inherits: base_work
        calendar_name: Tasks

Inheritance is recursive: a section can inherit from a section that itself
inherits from another.

Meta-sections (collections)
============================

A section with a ``contains`` key is a *meta-section*: it groups other
sections together.  :func:`~caldav.davclient.get_calendars` with a meta-section will
aggregate calendars from all listed sections, including across multiple servers:

.. code-block:: yaml

    personal:
        caldav_url: https://personal.example.com/
        caldav_username: alice
        caldav_password: secret1

    work:
        caldav_url: https://work.example.com/
        caldav_username: alice
        caldav_password: secret2

    all:
        contains:
            - personal
            - work

Calling ``get_calendars(config_section="all")`` returns calendars from both
servers.  Meta-sections are resolved recursively, so a meta-section may
contain other meta-sections.  Circular references are detected and ignored.

A section can also be disabled so it is skipped during expansion:

.. code-block:: yaml

    old_server:
        disable: true
        caldav_url: https://old.example.com/

Glob patterns and wildcards
----------------------------

Instead of listing sections explicitly, ``contains`` may use glob patterns,
and the ``config_section`` argument (or ``CALDAV_CONFIG_SECTION``) itself may
be a glob or ``*``:

.. code-block:: yaml

    work_inbox:
        caldav_url: https://work.example.com/
        caldav_username: alice
        caldav_password: secret
        calendar_name: Inbox

    work_tasks:
        caldav_url: https://work.example.com/
        caldav_username: alice
        caldav_password: secret
        calendar_name: Tasks

    all_work:
        contains:
            - work_*

``get_calendars(config_section="work_*")`` and
``get_calendars(config_section="all_work")`` are therefore equivalent.
``get_calendars(config_section="*")`` returns calendars from every
non-disabled section in the file.

Environment variables
=====================

Connection parameters can also be passed via environment variables without a
config file.  The variables are mapped as follows:

.. list-table::
   :header-rows: 1

   * - Environment variable
     - Parameter
   * - ``CALDAV_URL``
     - ``url``
   * - ``CALDAV_USERNAME`` or ``CALDAV_USER``
     - ``username``
   * - ``CALDAV_PASSWORD`` or ``CALDAV_PASS``
     - ``password``
   * - ``CALDAV_CONFIG_FILE``
     - Path to config file
   * - ``CALDAV_CONFIG_SECTION``
     - Section name (may be a glob)

Examples
========

Minimal single-server config
-----------------------------

.. code-block:: yaml

    ---
    default:
        caldav_url: https://caldav.example.com/dav/
        caldav_username: alice
        caldav_password: secret

Multiple servers aggregated under one name
------------------------------------------

.. code-block:: yaml

    ---
    personal:
        caldav_url: https://personal.example.com/
        caldav_username: alice
        caldav_password: secret1
        features: xandikos

    work:
        caldav_url: https://work.example.com/
        caldav_username: alice.work
        caldav_password: secret2

    all:
        contains:
            - personal
            - work

Shared base with per-calendar overrides
----------------------------------------

.. code-block:: yaml

    ---
    _server: &server
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password: secret

    inbox:
        inherits: _server
        calendar_name: Inbox

    tasks:
        inherits: _server
        calendar_name: Tasks
        calendar_url: https://caldav.example.com/cal/tasks/
