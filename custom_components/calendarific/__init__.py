"""Calendarific Platform"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_STATE,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
)
from .coordinator import CalendarificConfigEntry, CalendarificCoordinator
from .helpers import instance_unique_id

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Set up a Calendarific instance (one country/state combination) from a config entry."""
    if CONF_API_KEY not in entry.data:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="legacy_entry"
        )

    coordinator = CalendarificCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Bring an older config entry up to the current schema."""
    if entry.version > CONFIG_ENTRY_VERSION:
        # Created by a newer release; don't guess at its layout.
        return False

    if entry.minor_version < 2:
        # Minor 2: identify each instance by its country/state.
        unique_id: str | None = None
        if CONF_COUNTRY in entry.data:
            candidate = instance_unique_id(
                entry.data[CONF_COUNTRY], entry.data.get(CONF_STATE, "")
            )
            if any(
                other.unique_id == candidate
                for other in hass.config_entries.async_entries(DOMAIN)
                if other.entry_id != entry.entry_id
            ):
                # Duplicate instances were possible before; keep the later ones
                # working without an ID rather than refusing to load them.
                _LOGGER.warning(
                    "Calendarific instance %s duplicates another instance's "
                    "country and state, so it has no unique ID; consider removing it",
                    entry.title,
                )
            else:
                unique_id = candidate
        hass.config_entries.async_update_entry(
            entry, unique_id=unique_id, minor_version=2
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
