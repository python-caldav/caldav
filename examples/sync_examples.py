## Some example pseudo code ... first, keep a running python process
## with the full calendar cached locally, and list out the summary
## lines of every object:

my_events = cal_obj.objects_by_sync_token(load_objects=True)
# (... some time later ...)
my_events.sync()
for event in my_events:
    print(event.icalendar.subcomponents[0]['SUMMARY'])


## Code for keeping a local database of events in sync with a remote
## caldav server:

my_events = cal_obj.objects_by_sync_token()
for event in my_events:
     save_event_to_database(event)
save_sync_token_to_database(my_events.sync_token)
# (... some time later ...)
sync_token = load_sync_token_from_database()
my_updated_events = cal_obj.objects_by_sync_token(sync_token)
for event in my_updated_events:
    if event.is_deleted:
        delete_event_from_database(event)
    else:
        update_event_in_database(event)
