"""Calendarific Platform"""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_DEFAULTS,
    CONF_HOLIDAYS,
    CONF_STATE,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
)
from .coordinator import CalendarificConfigEntry, CalendarificCoordinator
from .helpers import (
    calendar_unique_id,
    holiday_unique_id,
    instance_unique_id,
    next_holiday_unique_id,
)
from .issues import async_delete_issues

PLATFORMS = [Platform.SENSOR, Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)

# The free-text unit setting that minor version 3 removed.
_LEGACY_UNIT_KEY = "unit_of_measurement"


async def async_setup_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Set up a Calendarific instance (one country/state combination) from a config entry."""
    if CONF_API_KEY not in entry.data:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="legacy_entry"
        )

    coordinator = CalendarificCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _async_remove_stale_entities(hass, entry)
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

    if entry.minor_version < 3:
        # Minor 3: the unit is always days, so the stored setting goes.
        options = dict(entry.options)
        if isinstance(defaults := options.get(CONF_DEFAULTS), dict):
            options[CONF_DEFAULTS] = {
                key: value for key, value in defaults.items() if key != _LEGACY_UNIT_KEY
            }
        if isinstance(holidays := options.get(CONF_HOLIDAYS), dict):
            options[CONF_HOLIDAYS] = {
                name: {key: value for key, value in override.items() if key != _LEGACY_UNIT_KEY}
                for name, override in holidays.items()
            }
        hass.config_entries.async_update_entry(entry, options=options, minor_version=3)

    return True


@callback
def _async_remove_stale_entities(hass: HomeAssistant, entry: CalendarificConfigEntry) -> None:
    """Delete entities of holidays the instance no longer tracks."""
    expected = {
        holiday_unique_id(entry.entry_id, name) for name in entry.options.get(CONF_HOLIDAYS, {})
    } | {next_holiday_unique_id(entry.entry_id), calendar_unique_id(entry.entry_id)}
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in expected:
            registry.async_remove(entity.entity_id)


async def async_remove_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> None:
    """Clear the repair issues of a deleted instance."""
    async_delete_issues(hass, entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CalendarificConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
