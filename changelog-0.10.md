# Changelog v0.9.2 -> v0.10

## Quick summary

* Work on a universal search method
  * Refactoring, consolidated lots of slightly duplicated code into one method to rule them all
  * Support for things needed by the calendar-cli utility, like search by categories
* Other improvements:
  * Picklable URLs
  * display_name convenience method

## Github issues and pull requests

https://github.com/python-caldav/caldav/pull/204
https://github.com/python-caldav/caldav/pull/208
https://github.com/python-caldav/caldav/pull/212

## Commits

8d9a36d004d983b2423e8d33d756ecbc0022e8c5 - allow requests timeout (Marcel Schwarz)
2ac6cb7a4c256e6f42316336d66aef4a8f100867 - make URLs pickable (Ryan Nowakowski)
b4464cd57f696a783ef7c90ee9640c2f5ee8408b - black style fixup ^
1f007a443393ea74b1ecb811464b7c8706051496 - get_display_name convenience method (mc-borscht)
1d639eb94fe902d3fa86a3558154264267cd384b - get_display_name revisited
57fdf04a6019f8d811e0f1b7c3b5ecfd21ed44ce - black style fixup ^
