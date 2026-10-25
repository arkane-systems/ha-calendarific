"""Keeps holiday sensors' friendly names plain on newer Home Assistant releases.

Since Home Assistant 2026.10, the state's friendly_name (what templates, voice
assistants and automations see) is "<device name> <entity name>" for every
entity that has a device, so a holiday sensor would read "Home Christmas Day".
There is no supported way for an integration to opt out, but a name stored in
the entity registry (what a user rename sets) is used verbatim. We store the
holiday's own name there, which leaves the prefixed entity ID alone and makes
no difference on older releases, where the friendly name is already plain.

A name the user chose themselves is never overwritten.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_HOLIDAYS, DOMAIN
from .helpers import holiday_unique_id


def _wanted_names(entry: ConfigEntry) -> dict[str, str]:
    """Map each holiday sensor's unique ID to the name it should be shown as."""
    holidays: dict[str, dict[str, str]] = entry.options.get(CONF_HOLIDAYS, {})
    return {
        holiday_unique_id(entry.entry_id, holiday): override.get(CONF_NAME) or holiday
        for holiday, override in holidays.items()
    }


@callback
def async_snapshot_registered_names(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str | None]:
    """Record the names the holiday sensors registered under last time.

    Take this before the platforms are set up, which replaces them. A registry
    name equal to the previous registered name is one this integration wrote.
    """
    registry = er.async_get(hass)
    previous: dict[str, str | None] = {}
    for unique_id in _wanted_names(entry):
        entity_id = registry.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
        if entity_id is not None and (registered := registry.async_get(entity_id)):
            previous[unique_id] = registered.original_name
    return previous


@callback
def async_apply_plain_names(
    hass: HomeAssistant, entry: ConfigEntry, previous: dict[str, str | None]
) -> None:
    """Store each holiday sensor's display name as its registry name."""
    registry = er.async_get(hass)
    for unique_id, wanted in _wanted_names(entry).items():
        entity_id = registry.async_get_entity_id(Platform.SENSOR, DOMAIN, unique_id)
        if entity_id is None or (registered := registry.async_get(entity_id)) is None:
            continue
        current = registered.name
        if current == wanted:
            continue
        # Empty (new entity, upgrade, or a reset in the UI), or still the name we
        # wrote before the custom name changed. Anything else is the user's own.
        if current is None or current == previous.get(unique_id):
            registry.async_update_entity(entity_id, name=wanted)
