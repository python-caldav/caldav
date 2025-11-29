#!/usr/bin/env python
"""
I got fed up with several thousand lines of code in one and the same file.

This file is by now just a backward compatibility layer.

Logic has been split out:

* DAVObject base class -> davobject.py
* CalendarObjectResource base class -> calendarobjectresource.py
* Event/Todo/Journal/FreeBusy -> calendarobjectresource.py
* Everything else (mostly collection objects) -> collection.py

The async-first implementation lives in _async/ and _sync/ subdirectories.
This module exports the sync (backward-compatible) versions.
"""
## For backward compatibility - import from original modules
## These will be gradually migrated to use the _sync wrappers
from .calendarobjectresource import *
from .collection import *
from .davobject import *
