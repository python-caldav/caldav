As of 3.x, quite some methods in classes like Calendar, Event, etc are dual-mode sync/async.  They will return an awaitable coroutine when run in async mode, and a value when run in sync mode.  (I haven't decided how to do this in 4.x.  Claude suggests to write async first and then auto-generate the sync code.  I still think it may be worth doing more research into the "Sans-IO" code pattern).

Claude seems happy with copying code and making async-versions of the sync code.  (and then later, when adding new features or fixing bugs, it will be done on only on the sync version - or only on the async version, whatever is in focus that day).  I really hate code duplication - but for the methods that are mixing many I/O-calls with a bit of data processing, this seems to be the only trivial option.  **Such methods should be marked up with inline comments, warning that the code is duplicated and that any changes should be mirrored in the other code path**.

As for 3.x, for a method `foo` doing some preparations, some IO and then some processing of the data, those rules should be applied:

* `foo` should *always* do the
  `if self.is_async_client: return self._async_foo(...)`-logic
* `foo` should have type hints telling it may return an awaitable coroutine
* `self._async_foo` should never be called upon other places
* Quite many of the methods are doing some preparations, firing off
  some other method causing I/O, and then doing some processing of
  the data returned from the server.  Other methods are more complex,
  having mutliple code lines causing I/O.
* For methods containing significant amount of logic (like, two or
  more code lines) before doing any IO, the
  `if self.is_async_client: return self._async_foo(...)`-logic
  should be moved to the last possible point in the method. * For methods
  containing significant amount of logic after doing the IO, split the
  logic out in a `_post_foo`-method.
