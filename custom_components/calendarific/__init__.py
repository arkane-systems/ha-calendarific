"""Calendarific Platform"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .api import CalendarificApiReader
from .const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_STATE,
    DOMAIN,
    SENSOR_PLATFORM,
)

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Calendarific instance (one country/state combination) from a config entry."""
    if CONF_API_KEY not in entry.data:
        raise ConfigEntryError(
            "This entry was created by an older version of Calendarific and is no "
            "longer compatible. Please remove it and add the integration again."
        )

    reader = await hass.async_add_executor_job(
        CalendarificApiReader,
        entry.data[CONF_API_KEY],
        entry.data[CONF_COUNTRY],
        entry.data[CONF_STATE],
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "apiReader": reader,
        SENSOR_PLATFORM: {},
    }
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options (e.g. selected holidays) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
