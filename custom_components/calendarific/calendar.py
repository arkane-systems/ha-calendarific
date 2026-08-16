# Adapted from  bruxy70/Garbage-Collection
# https://github.com/bruxy70/Garbage-Collection/blob/master/custom_components/garbage_collection/calendar.py

"""Calendarific calendar."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DOMAIN, SENSOR_PLATFORM
from .device import get_device_info

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up this instance's calendar (one per config entry)."""
    async_add_entities([CalendarificCalendar(entry)], True)


class CalendarificCalendar(CalendarEntity):
    """Calendar collecting the holidays of a single Calendarific instance."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Create empty calendar for this instance."""
        self._entry = entry
        self._cal_data = EntitiesCalendarData(entry)

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this calendar."""
        return f"{self._entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._cal_data.event

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._entry.title

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to group with this instance's sensors."""
        return get_device_info(self._entry)

    async def async_update(self) -> None:
        """Update the calendar."""
        await self._cal_data.async_update(self.hass)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        return await self._cal_data.async_get_events(hass, start_date, end_date)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the device state attributes."""
        if self._cal_data.event is None:
            # No tasks, we don't need to show anything.
            return None
        return {}


class EntitiesCalendarData:
    """Aggregates one instance's holiday sensors into calendar events."""

    # "_throttle" isn't set here directly - the @Throttle decorator on
    # async_update sets it dynamically on first call, so it must still be
    # declared or that assignment fails with no __dict__ to fall back on.
    __slots__ = "_entry", "event", "_throttle"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize an Entities Calendar Data."""
        self._entry = entry
        self.event: CalendarEvent | None = None

    def _entities(self, hass: HomeAssistant):
        """Return this instance's live sensor entities, keyed by entity_id."""
        return hass.data[DOMAIN][self._entry.entry_id][SENSOR_PLATFORM]

    async def async_get_events(
        self, hass: HomeAssistant, start_datetime: datetime, end_datetime: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events: list[CalendarEvent] = []
        start_date = start_datetime.date()
        end_date = end_datetime.date()
        for entity in self._entities(hass).values():
            if (
                entity.name
                and entity._date
                and entity._date != "-"
                and start_date <= entity._date <= end_date
            ):
                event = CalendarEvent(
                    summary=entity.name,
                    start=entity._date,
                    end=entity._date + timedelta(days=1),
                    description=entity.extra_state_attributes["description"]
                    if "description" in entity.extra_state_attributes
                    else None,
                )
                events.append(event)
        return events

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, hass: HomeAssistant) -> None:
        """Get the latest data."""
        for entity in self._entities(hass).values():
            if entity.name and entity._date and entity._date != "-":
                self.event = CalendarEvent(
                    summary=entity.name,
                    start=entity._date,
                    end=entity._date + timedelta(days=1),
                    description=entity.extra_state_attributes["description"]
                    if "description" in entity.extra_state_attributes
                    else None,
                )
