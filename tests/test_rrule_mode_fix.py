from unittest.mock import MagicMock, patch

import pytest

from caldav.calendarobjectresource import Todo


@pytest.mark.parametrize("mode", ["this_and_future", "thisandfuture"])
def test_recurring_mode_spelling(mode):
    todo = object.__new__(Todo)

    todo._icalendar_instance = MagicMock()
    todo._icalendar_instance.subcomponents = []

    with patch.object(Todo, "is_async_client", False):
        with patch.object(Todo, "icalendar_component", {"RRULE": True}):
            with patch.object(Todo, "_complete_recurring_thisandfuture") as complete:
                todo.complete(handle_rrule=True, rrule_mode=mode)
                complete.assert_called_once()


from unittest.mock import AsyncMock


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["this_and_future", "thisandfuture"])
async def test_async_recurring_mode_spelling(mode):
    todo = object.__new__(Todo)

    todo._icalendar_instance = MagicMock()
    todo._icalendar_instance.subcomponents = []

    with patch.object(Todo, "is_async_client", True):
        with patch.object(
            Todo, "_async_complete", new_callable=AsyncMock
        ) as async_complete:
            result = todo.complete(handle_rrule=True, rrule_mode=mode)
            await result

            async_complete.assert_awaited_once()
            assert async_complete.await_args.args[2] == "thisandfuture"
