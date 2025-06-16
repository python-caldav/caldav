
==========
 Examples
==========

There is an example directory in the source of the project, some of the examples is written by the maintainer, others are written by other contributors - with or without a bit of brush-up from the maintainer to make things a bit more in line with "the best current practices".  I'm striving to make the examples redundant, the documentation should contain all you need to know - but it may be worth having a look into actual code if you're stuck.

View the examples on `github <https://github.com/python-caldav/caldav/tree/master/examples>`_

Files currently there:

* ``basic_usage_examples.py`` - written by the maintainer - contains all you need to know to do basic calendar interactions.  Code is regularly tested towards the Radicale server in the unit tests.
* ``get_events_example.py`` - written by Krylov Alexandr, with lots of comments from the maintainer.  Code is regularly tested towards the Radicale server in the unit tests.
* ``scheduling_examples.py`` - This is NOT tested, it may or may not work!  (I should look into this soon)
* ``sync_examples.py`` - this is "pseudo-code", not intended to work, and hence not tested.  I'm also planning on making a HOWTO on how to backup your calendar locally.
* ``google-flask.py`` some flask application reading content from a Google calendar.  Contributed by @seidnerj, not tested by the caldav maintainer.
* ``google-django`` - some python code utilizing django allauth library to authenticate towards a Google calendar.   Contributed by Abe Hanoka, not tested by the caldav maintainer.
* ``google-service-account`` - some python code utilizing a Google service account for authentication.  Contributed by Bo Lopker, not tested by the caldav maintainer.
