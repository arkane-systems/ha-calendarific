"""Base entity for Calendarific."""

from __future__ import annotations

from datetime import date

from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, CONF_HOLIDAYS
from .coordinator import CalendarificCoordinator
from .device import get_device_info


class CalendarificEntity(CoordinatorEntity[CalendarificCoordinator]):
    """Common behavior of every Calendarific entity."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: CalendarificCoordinator) -> None:
        """Initialize the entity and group it under its instance's device."""
        super().__init__(coordinator)
        self._attr_device_info = get_device_info(coordinator.config_entry)

    @property
    def _tracked_holidays(self) -> dict[str, dict[str, object]]:
        """The holidays this instance tracks, with their per-holiday overrides."""
        holidays: dict[str, dict[str, object]] = self.coordinator.config_entry.options.get(
            CONF_HOLIDAYS, {}
        )
        return holidays

    def _display_name(self, holiday_name: str) -> str:
        """The user's custom name for a tracked holiday, or the holiday's own name."""
        override = self._tracked_holidays.get(holiday_name, {})
        return str(override.get(CONF_NAME) or holiday_name)

    @staticmethod
    def _today() -> date:
        """Today in Home Assistant's configured time zone, not the system clock's."""
        return dt_util.now().date()
