"""Shared device info helper for Calendarific entities."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_COUNTRY, CONF_STATE, DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL


def get_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo grouping all of one instance's entities under one device.

    Keyed by entry_id so every entity belonging to this config entry (this
    country/state instance) - however many holidays it holds - shares a
    single device, and separate instances never collide.
    """
    country = entry.data.get(CONF_COUNTRY, "")
    state = entry.data.get(CONF_STATE, "")

    device_name = entry.title or DEVICE_MANUFACTURER
    if not entry.title and country:
        device_name += f" ({country.upper()}"
        if state:
            device_name += f" - {state.upper()}"
        device_name += ")"

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=device_name,
        manufacturer=DEVICE_MANUFACTURER,
        model=DEVICE_MODEL,
    )
