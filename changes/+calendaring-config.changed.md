The config file is now read through the [calendaring-config](https://github.com/pycalendar/calendaring-config) package, which the file's other users (plann, calendaring) share; see https://github.com/python-caldav/caldav/issues/786.  This is a new dependency, `calendaring-config>=0.3` (it depends only on PyYAML), which matters to packagers.  New in the format:

- `~/.config/pycal/calendar.yaml` is searched first, before the old paths.
- A section may say `kind: caldav` and drop the `caldav_` prefix.  Sections of other kinds (`kind: jmap`, a directory of `.ics` files) are skipped.
- `password_command` runs a program for the password, and `password_keyring` looks it up in the system keyring.
- `CALDAV_*` environment variables override the section's keys one by one: a `CALDAV_PASSWORD` alone no longer makes caldav ignore the config file (https://github.com/python-caldav/caldav/issues/780).  `true`/`false` in a variable is a boolean now, and `CALDAV_HEADERS` is read as JSON.
- `extract_conn_params_from_section()`, which plann uses, reads the new format too; pass it the config file's path as `config_file` to let a `password_command` run, and the section's name as `section_name` for error messages.
- An unknown key in a section is logged as a warning.  `x_*` and `extra_config` are reserved for applications.
