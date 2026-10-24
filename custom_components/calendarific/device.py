"""Shared device info helper for Calendarific entities."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    CONF_COUNTRY,
    CONF_STATE,
    CONFIGURATION_URL,
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
)
from .helpers import default_title


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo grouping all of one instance's entities under one device.

    Keyed by entry_id so every entity belonging to this config entry (this
    country/state instance) - however many holidays it holds - shares a
    single device, and separate instances never collide.
    """
    country = entry.data.get(CONF_COUNTRY, "")
    if entry.title:
        name = entry.title
    elif country:
        name = default_title(country, entry.data.get(CONF_STATE, ""))
    else:
        name = DEVICE_MANUFACTURER

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=name,
        manufacturer=DEVICE_MANUFACTURER,
        model=DEVICE_MODEL,
        entry_type=DeviceEntryType.SERVICE,
        configuration_url=CONFIGURATION_URL,
    )
