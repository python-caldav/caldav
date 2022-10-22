# Changelog v0.9.2 -> v0.10

## Quick summary

* Work on a universal search method
  * Refactoring, consolidated lots of slightly duplicated code into one method to rule them all
  * Support for things needed by the calendar-cli utility, like search by categories
* Support for completion of recurring tasks
* More utilities for tasks
  * Uncomplete-method ... for undoing the complete (recurrences not supported though)
  * get/set duration/dtstart/dtend (arguably this belongs to vobject and/or icalendar)
* Other improvements:
  * picklable URLs
  * display_name convenience method
  * possible to set child/parent relationships
* Potential bugfix: sequence number may need to be increased when saving something to the calendar (not backported, this may have side effects)

## Search method



## Completed tasks

While the RFCs do support recurring tasks, they are not very clear on the details.  In v0.10 there are three different ways to complete a task.  The first one is to ignore the RRULE property and mark the task as completed.  This is the backwards-compatibility mode - though, according to my understanding of a "recurring task" this is the wrong way to do it.

The two other modes considers the task to be "interval based" is no BY-rules are specified in the RRULE - meaning that if a task is supposed to be done weekly, then a week should pass from it was completed and until one needs to start with it again - no matter the DTSTART of the original instance - but the standards may also be interpreted so that if the original task was to be started at a Tuesday 10:00, then all recurrences should be started at a Tuesday 10:00.

Both the modes stores a copy of the completed task, for the record.  The "safe" mode stores the copy as a completely independent task, and modifies the DTSTART/DUE of the original task - so the completed task is not linked up to the recurring task.  (One may eventually try to make a link by establishing a "parent task").

The "thisandfuture"-mode will establish the completed task as a separate recurrence in a recurrence set.  The non-completed task is also duplicated with a new DTSTART set and range set to THISANDFUTURE. As I understand the RFC, this is the way to handle interval-based tasks, future recurrences will then base their starting time on the DTSTART of the THISANDFUTURE task.  For fixed tasks the THISANDFUTURE recurrence is moot, so I'm considering to create a third mode as well.

## Github issues and pull requests

https://github.com/python-caldav/caldav/pull/204
https://github.com/python-caldav/caldav/pull/208
https://github.com/python-caldav/caldav/pull/212
https://github.com/python-caldav/caldav/pull/216
https://github.com/python-caldav/caldav/issues/219
https://github.com/python-caldav/caldav/issues/16

## Commits

8d9a36d004d983b2423e8d33d756ecbc0022e8c5 - allow requests timeout (Marcel Schwarz)
2ac6cb7a4c256e6f42316336d66aef4a8f100867 - make URLs pickable (Ryan Nowakowski)
b4464cd57f696a783ef7c90ee9640c2f5ee8408b - style fixup
1f007a443393ea74b1ecb811464b7c8706051496 - get_display_name convenience method (mc-borscht)
1d639eb94fe902d3fa86a3558154264267cd384b - get_display_name revisited
57fdf04a6019f8d811e0f1b7c3b5ecfd21ed44ce - style fixup
25e9efae98746374e4e5753db2eb957b3f2a8f82 - test code
dea8eb50e86a9c36dcd1ca8b46b71eebec036437 - style fixup
2ed9b993a4fdcfaf8199a8a1301b2a4fb5b6fa03 - test code
a853c03956d59533d566ed696848e69924d4d207 - search method
62531ead3ad95a95c0b944f4fcfae9700d843b42 - changelog
485561d1f46d1de9460fb9262294ea48b7b3f0e0 - test code (plus some compatibility fixes, already backported to v0.9)
0c6ccfff623a3e53c05f1d91e4fcc4be64fbe4bf - changelog
9044c90e35908a353c872d8fb97729e9f162f588 - test code
6572d93b6d167c72ba1c533b8505c0969f3d1b0f - search method
05b22708d8a84835b818efcbdba0b4fdeff52b32 - fixup
994c572f958ef8575921c701a20e0443384927ae - test code
b8358adb1686cfabfe7f90e342f09fc3ea53facb - test code
3cfaacdb10ed0f1ce48b288d3c49e4c9b4ef7b74 - test code
24e340074f1341f3ffea64dd05ed87f659e78cb4 - test code
96d65509c2f0f431a81af7128c974450d84d9cd4 - style fixup
5c2cf8129a23a2eac468c5937d29ec42f88dc059 - undo complete
84c4d03135f78b63cf005e529e28b7c304f36015 - style fixup
e60de3b84b36e279f8723eb7c8c1ddb7fa6e3f49 - parent/child relationships
cd3c07472bc96ce3dde5a40fa0752da86a1d7559 - recurring complete
2148891187c1083258edd371fc63026daf33a357 - fixup recurring complete
b21a2c6fe5a081bee29ec1e238d2c75235e51f41 - fixup recurring complete
24e024f0576308bd631f0b5ccd06d3007682cc7e - style fixup
ec15e2762b23232705deb5ce43a0b4693acf1f3b - fixup recurring complete
534d0fde36a3cd5b6eaa1692458f124cdbb64f16 - style fixup
e4b38ef9197a78c5ca2ca518c2e01b54fc58b0eb - fixup for search
20c2a293ee8cb227dc6ff1be0faeddd62a999b15 - style fixup
e723d88af9337d0af5772214a8c4d7f150943a8e - test code
e9c45819a74c6fa3a775f8fcb6e797b0a4839711 - sequence number to be increased
65920b592220e70561e33beadbbd17028e5b6e65 - style fixup
452d0df5f93c26575ff0a35ffe0e81dc26923bc4 - test code
d51c5f9c51a04a6872ebc5c15cffbd7018d7393b - icalendar is now an official dependency
b5bd38e944f563a547b693c676b8800734b3ec7a - style fixup (or breakdown)
7232e69972950d092f1fdda4779234ce206d5da0 - docfix