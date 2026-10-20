The config file is now read through the [calendaring-config](https://github.com/pycalendar/calendaring-config) package, which the file's other users (plann, calendaring) share; see https://github.com/python-caldav/caldav/issues/786.  New in the format:

- `~/.config/pycal/calendar.yaml` is searched first, before the old paths.
- A section may say `kind: caldav` and drop the `caldav_` prefix.  Sections of other kinds (`kind: jmap`, a directory of `.ics` files) are skipped.
- `password_command` runs a program for the password, and `password_keyring` looks it up in the system keyring.
- `CALDAV_*` environment variables override the section's keys one by one: a `CALDAV_PASSWORD` alone no longer makes caldav ignore the config file (https://github.com/python-caldav/caldav/issues/780).  `true`/`false` in a variable is a boolean now, and `CALDAV_HEADERS` is read as JSON.
- `extract_conn_params_from_section()`, which plann uses, reads the new format too; pass it the config file's path as `config_file` to let a `password_command` run.
- An unknown key in a section is logged as a warning.  `test_*`, `x_*` and `extra_config` are reserved for test tooling and applications.

Some files are read differently: an empty file found first is used, rather than skipped for the next one; a section named directly that is missing or disabled, or a glob that matches nothing, is an error; a name in `contains` that matches nothing gives a warning; a disabled meta-section leaves out its members too; `*` is only the sections that are not meta-sections; and a config file named explicitly must exist.
