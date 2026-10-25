"""Calendarific calendar."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Holiday
from .coordinator import CalendarificConfigEntry, CalendarificCoordinator
from .entity import CalendarificEntity
from .helpers import calendar_unique_id

# The calendar reads from the coordinator and never talks to the API itself.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalendarificConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this instance's calendar (one per config entry)."""
    async_add_entities([CalendarificCalendar(entry.runtime_data)])


class CalendarificCalendar(CalendarificEntity, CalendarEntity):
    """Calendar of the holidays a single Calendarific instance tracks."""

    # The instance's one calendar is its main feature, so it takes the device's name.
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "holidays"

    def __init__(self, coordinator: CalendarificCoordinator) -> None:
        """Initialize the calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = calendar_unique_id(coordinator.config_entry.entry_id)

    def _to_event(self, holiday: Holiday) -> CalendarEvent:
        return CalendarEvent(
            summary=self._display_name(holiday.name),
            start=holiday.day,
            end=holiday.day + timedelta(days=1),
            description=holiday.description,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming holiday."""
        holiday = self.coordinator.data.next_holiday(self._tracked_holidays, self._today())
        return None if holiday is None else self._to_event(holiday)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the tracked holidays that fall within the given time frame."""
        holidays = self.coordinator.data.occurrences(
            self._tracked_holidays, start_date.date(), end_date.date()
        )
        return [
            self._to_event(holiday)
            for holiday in holidays
            if dt_util.start_of_local_day(holiday.day) < end_date
            and dt_util.start_of_local_day(holiday.day + timedelta(days=1)) > start_date
        ]
