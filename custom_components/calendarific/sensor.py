"""Calendarific sensors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import Holiday
from .const import (
    ATTR_DATE,
    ATTR_DAYS,
    ATTR_DESCRIPTION,
    CONF_DATE_FORMAT,
    CONF_DEFAULTS,
    CONF_HOLIDAYS,
    CONF_ICON_NORMAL,
    CONF_ICON_SOON,
    CONF_ICON_TODAY,
    CONF_SOON,
    DEFAULT_DATE_FORMAT,
    DEFAULT_ICON_NORMAL,
    DEFAULT_ICON_SOON,
    DEFAULT_ICON_TODAY,
    DEFAULT_SOON,
)
from .coordinator import CalendarificConfigEntry, CalendarificCoordinator
from .entity import CalendarificEntity
from .helpers import holiday_unique_id, next_holiday_unique_id

# Entities read from the coordinator and never talk to the API themselves.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CalendarificConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one sensor per holiday selected for this instance, plus a next-holiday sensor."""
    coordinator = entry.runtime_data
    defaults = entry.options.get(CONF_DEFAULTS, {})
    holidays = entry.options.get(CONF_HOLIDAYS, {})
    entities: list[SensorEntity] = [
        # Sparse per-holiday overrides win; anything unset falls back to the
        # instance's defaults.
        HolidaySensor(coordinator, holiday_name, {**defaults, **override})
        for holiday_name, override in holidays.items()
    ]
    entities.append(NextHolidaySensor(coordinator))
    async_add_entities(entities)


class HolidaySensor(CalendarificEntity, SensorEntity):
    """Counts down the days to one tracked holiday."""

    # Named after the holiday itself, not prefixed with the instance (see
    # has-entity-name in quality_scale.yaml).
    _attr_has_entity_name = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS

    def __init__(
        self,
        coordinator: CalendarificCoordinator,
        holiday_name: str,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize the sensor from the holiday's resolved settings."""
        super().__init__(coordinator)
        self._holiday = holiday_name
        self._icon_normal: str = config.get(CONF_ICON_NORMAL, DEFAULT_ICON_NORMAL)
        self._icon_today: str = config.get(CONF_ICON_TODAY, DEFAULT_ICON_TODAY)
        self._icon_soon: str = config.get(CONF_ICON_SOON, DEFAULT_ICON_SOON)
        self._soon: int = config.get(CONF_SOON, DEFAULT_SOON)
        self._date_format: str = config.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)
        self._attr_name = config.get(CONF_NAME) or holiday_name
        self._attr_unique_id = holiday_unique_id(coordinator.config_entry.entry_id, holiday_name)

    def _next(self) -> Holiday | None:
        return self.coordinator.data.next_occurrence(self._holiday, self._today())

    @property
    def native_value(self) -> int | None:
        """Return the number of days until the holiday, or None if it is not known."""
        holiday = self._next()
        return None if holiday is None else (holiday.day - self._today()).days

    @property
    def icon(self) -> str:
        """Return the icon for today, soon or normal."""
        days = self.native_value
        if days is None:
            return self._icon_normal
        if days == 0:
            return self._icon_today
        if days <= self._soon:
            return self._icon_soon
        return self._icon_normal

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the holiday's next date and description."""
        holiday = self._next()
        if holiday is None:
            return {ATTR_DATE: None, ATTR_DESCRIPTION: None}
        return {
            ATTR_DATE: holiday.day.strftime(self._date_format),
            ATTR_DESCRIPTION: holiday.description,
        }


class NextHolidaySensor(CalendarificEntity, SensorEntity):
    """Reports whichever tracked holiday is coming up soonest."""

    # Prefixed with the instance's name, which tells several instances' sensors apart.
    _attr_has_entity_name = True
    _attr_translation_key = "next_holiday"

    def __init__(self, coordinator: CalendarificCoordinator) -> None:
        """Initialize the sensor; there is one per instance."""
        super().__init__(coordinator)
        self._attr_unique_id = next_holiday_unique_id(coordinator.config_entry.entry_id)

    def _next(self) -> Holiday | None:
        return self.coordinator.data.next_holiday(self._tracked_holidays, self._today())

    @property
    def native_value(self) -> str | None:
        """Return the name of the soonest tracked holiday (its custom name, if any)."""
        holiday = self._next()
        return None if holiday is None else self._display_name(holiday.name)

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        """Return the days remaining until that holiday."""
        holiday = self._next()
        return {ATTR_DAYS: None if holiday is None else (holiday.day - self._today()).days}
