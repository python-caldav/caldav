## Some example pseudo code ("pseudo" meaning I haven't actually
## verified that the following code works - but there exists some
## similar code in the tests/test_caldav.py file.  Raise a github
## issue or reach out by email or write a pull request or send a patch
## if there are mistakes in this code) ...
## USE CASE #1: we'll have a local copy of all calendar contents in a
## running python process, and later we'd like to synchronize the
## local contents.  (In case of a reboot, all contents will be
## downloaded again).

my_events = my_calendar.objects(load_objects=True)
# (... some time later ...)
my_events.sync()
for event in my_events:
    print(event.icalendar.subcomponents[0]["SUMMARY"])

## USE CASE #2, approach #1: We want to load all objects from the
## remote caldav server and insert them into a database.  Later we
## need to do one-way syncing from the remote caldav server into the
## database.
my_events = my_calendar.objects(load_objects=True)
for event in my_events:
    save_event_to_database(event)
save_sync_token_to_database(my_events.sync_token)

# (... some time later ...)

sync_token = load_sync_token_from_database()
my_updated_events = my_calendar.objects_by_sync_token(sync_token, load_objects=True)
for event in my_updated_events:
    if event.data is None:
        delete_event_from_database(event)
    else:
        update_event_in_database(event)
save_sync_token_to_database(my_updated_events.sync_token)

## USE CASE #2, approach #2, using my_events.sync().  Ref
## https://github.com/python-caldav/caldav/issues/122 this may be
## significantly faster if the caldav server tends to discard sync
## tokens or if the remote caldav server supports etags but not sync
## tokens.
my_events = my_calendar.objects(load_objects=True)
for event in my_events:
    save_event_to_database(event)
save_sync_token_to_database(my_events.sync_token)

# (... some time later ...)

updated, deleted = my_events.sync()
for event in updated:
    update_event_in_database(event)
for event in deleted:
    delete_event_in_database(event)
save_sync_token_to_database(my_events.sync_token)

## ... but the approach above gets a bit tricky when the server is
## rebooted/restarted.  It may be possible to save the etags in the
## database, eventually.  Feel free to raise a github issue or contact
## me privately if you need more support.

## Tobias Brox, 2020-12-28
