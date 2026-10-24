"""Calendarific Platform"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import CONF_API_KEY
from .coordinator import CalendarificConfigEntry, CalendarificCoordinator

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Set up a Calendarific instance (one country/state combination) from a config entry."""
    if CONF_API_KEY not in entry.data:
        raise ConfigEntryError(
            "This entry was created by an older version of Calendarific and is no "
            "longer compatible. Please remove it and add the integration again."
        )

    coordinator = CalendarificCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
