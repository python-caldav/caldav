==================
Config file format
==================

The :func:`caldav.davclient.get_davclient`, :func:`caldav.davclient.get_calendar`, and
:func:`caldav.davclient.get_calendars` functions read connection parameters from a config
file.  The file is shared with other programs, such as plann and
calendaring, and is read through the `calendaring-config
<https://github.com/pycalendar/calendaring-config>`_ package, whose
``docs/format.md`` is the full specification.  The file is searched in the
following locations (the first that exists is used, even if it is empty):

* ``$XDG_CONFIG_HOME/pycal/calendar.yaml`` (``$HOME/.config/pycal/calendar.yaml``)
* ``$HOME/.config/caldav/calendar.conf``
* ``$HOME/.config/caldav/calendar.yaml``
* ``$HOME/.config/caldav/calendar.json``
* ``$HOME/.config/calendar.conf``
* ``/etc/calendar.conf``
* ``/etc/caldav/calendar.conf``

The config file must be valid JSON or YAML.  The path can also be given
explicitly via the ``CALENDARING_CONFIG_FILE`` or ``CALDAV_CONFIG_FILE``
environment variable; a file named this way must exist.

Sections
========

The file is divided into named sections.  Each section contains key/value
pairs describing how to connect to a CalDAV server and optionally which
calendar to select.  The section to use is chosen as follows (first match
wins):

1. The ``config_section`` parameter passed to :func:`~caldav.davclient.get_davclient` /
   :func:`~caldav.davclient.get_calendars`.
2. The ``CALENDARING_CONFIG_SECTION`` or ``CALDAV_CONFIG_SECTION``
   environment variable.
3. The ``default`` section.

A section named this way that is missing or disabled is an error, except for
an implicit ``default``.

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
   * - ``caldav_auth_type``
     - ``auth_type``
     - ``basic``, ``digest`` or ``bearer``.  Usually not needed, but saves a
       round-trip to the server, and some servers need it to avoid an HTML
       login page being served on the first request.  For ``bearer``, the
       token goes in ``caldav_password``.

Any other parameter accepted by the :class:`~caldav.davclient.DAVClient`
constructor can be given the same way, as long as it is listed in
``caldav.config.CONNKEYS`` — currently also ``caldav_headers``,
``caldav_huge_tree``, ``caldav_ssl_cert``, ``caldav_enable_rfc6764`` and
``caldav_require_tls``.  (``auth`` is in that list too, but it takes an
authentication object and can therefore only be passed from code, not from a
config file.)

A section may instead say ``kind: caldav`` and leave out the prefix.  Such a
section can also describe the servers of other programs sharing the file
(``kind: jmap``, a directory of ``.ics`` files); caldav skips those.  A
section without ``kind`` and without ``caldav_`` keys is caldav's when its
``url`` is ``http://`` or ``https://``.

.. code-block:: yaml

    work:
        kind: caldav
        url: https://caldav.example.com/
        username: alice
        password_command: [pass, show, dav/work]

A key caldav does not know is logged as a warning and left out; see
`Reserved keys`_ for the keys other programs may put in a section.

The special ``features`` key (not prefixed with ``caldav_``) names a
server-compatibility profile — e.g. ``xandikos``, ``radicale``, ``baikal``.
See :mod:`caldav.compatibility_hints` for the full list of known profiles.
Various compatibility workarounds may be turned on or off depending on
the configured features.

Environment variable expansion
-------------------------------

Values may reference environment variables using ``${VAR}`` or
``${VAR:-default}`` syntax:

.. code-block:: yaml

    default:
        caldav_url: https://caldav.example.com/
        caldav_username: ${CALDAV_USER:-alice}
        caldav_password: ${CALDAV_PASSWORD}

Passwords from a command or the keyring
---------------------------------------

Instead of ``password`` (or ``caldav_password``), a section may give
``password_command``, a list of a program and its arguments whose output is
the password, or ``password_keyring``, a service name to look up in the
system keyring together with the username (this needs the ``keyring``
package).  The command is run without a shell, and only when the file is not
writable by group or others.

.. code-block:: yaml

    default:
        caldav_url: https://caldav.example.com/
        caldav_username: alice
        caldav_password_command: [pass, show, dav/work]

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
inherits from another.  A parent's ``contains`` and ``disable`` are not
inherited.  Inheriting from a missing section, a cycle of ``inherits``, or a
parent of another kind (a ``caldav_*`` section inheriting from a
``kind: jmap`` one) is an error.

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
A listed name that matches no section is skipped with a warning.

A section can also be disabled so it is skipped during expansion; a disabled
meta-section is skipped together with all its members:

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
non-disabled section in the file that is not a meta-section.  A glob that
matches no section is an error.

Reserved keys
=============

Some keys in a section are not caldav's, and caldav passes them by without
a warning:

* ``test_*`` is for test tooling;
* ``x_*`` is for an application's own settings;
* ``extra_config`` is plann's.

With ``testconfig=True`` (or the ``PYTHON_CALDAV_USE_TEST_SERVER``
environment variable), ``get_davclient()`` only uses sections marked with
``test_allowed: true``, so a personal server is never used for testing by
accident.  ``test_priority`` sets the order servers are tried in, lower
first; the default is 30, while embedded servers come at 10 and docker
servers at 20.

.. code-block:: yaml

    scratch_server:
        caldav_url: https://test.example.com/dav/
        caldav_username: tester
        caldav_password: secret
        test_allowed: true
        test_priority: 5

The older names ``testing_allowed`` and ``priority`` still work, but are
deprecated.

Environment variables
=====================

Every ``CALDAV_<KEY>`` environment variable is the key ``<key>`` of the
section, as if written in the config file: ``CALDAV_PASSWORD`` is
``password``, ``CALDAV_SSL_VERIFY_CERT`` is ``ssl_verify_cert``.
``CALDAV_USER`` and ``CALDAV_PASS`` are short for ``CALDAV_USERNAME`` and
``CALDAV_PASSWORD``.  Not keys are ``CALDAV_CONFIG_FILE`` and
``CALDAV_CONFIG_SECTION``, which choose the file and the section, and
``CALDAV_AUTH``, since ``auth`` takes an object.

* With ``CALDAV_URL`` set, the config file is not read at all: the
  connection is the one the variables describe.
* Otherwise, when the section is a single section, the variables override
  its keys one by one: ``CALDAV_PASSWORD`` alone keeps the URL from the
  file, and replaces a ``password_command`` there, which is then not run.
* When the section expands to several sections, the variables without a URL
  are not applied.

Environment variables are strings, and caldav converts them:
``true``/``yes``/``on``/``1`` and ``false``/``no``/``off``/``0`` become
booleans for ``ssl_verify_cert``, ``huge_tree``, ``enable_rfc6764`` and
``require_tls`` (``ssl_verify_cert`` may also be the path of a CA bundle),
``CALDAV_HEADERS`` is a JSON object, ``CALDAV_TIMEOUT`` a number, and
``CALDAV_FEATURES`` names a compatibility profile.  As in the file, a key
caldav does not know is logged as a warning.

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

Testing server compatibility
============================

The `caldav-server-tester <https://github.com/python-caldav/caldav-server-tester>`_
companion tool probes a CalDAV server and reports which features and RFC
requirements it supports, which ones it handles in a quirky way, and which ones
it gets wrong.  Its output can be used to populate the ``features`` key in your
config file so the caldav library applies the right workarounds automatically.

Installation::

    pip install caldav-server-tester

Run against a config section defined in your ``calendar.conf``::

    caldav-server-tester --config-section myserver

Or supply connection details directly::

    caldav-server-tester --caldav-url https://example.com/dav \
                         --caldav-username alice \
                         --caldav-password secret

The tool will run a series of checks and print which features deviate from the
CalDAV standard.  To get machine-readable output that you can paste into your
``calendar.conf``, use ``--format yaml``::

    caldav-server-tester --config-section myserver --format yaml

Copy the ``features:`` block from the output into your config section.
Alternatively, if your server matches one of the named profiles in
:mod:`caldav.compatibility_hints` (e.g. ``radicale``, ``baikal``,
``xandikos``), you can just name the profile::

    myserver:
        caldav_url: https://example.com/dav
        caldav_username: alice
        caldav_password: secret
        features: radicale
