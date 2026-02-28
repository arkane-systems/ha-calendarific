"""Shared device info helper for Calendarific entities."""
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, DEVICE_MANUFACTURER, DEVICE_MODEL


def get_device_info(domain_data: dict) -> DeviceInfo:
    """Return DeviceInfo to group all Calendarific entities under one device."""
    country = domain_data.get("country", "unknown")
    state = domain_data.get("state", "")

    device_id = f"{DOMAIN}_{country}"
    if state:
        device_id += f"_{state}"

    device_name = f"{DEVICE_MANUFACTURER}"
    if country:
        device_name += f" ({country.upper()}"
        if state:
            device_name += f" - {state.upper()}"
        device_name += ")"

    return DeviceInfo(
        identifiers={(DOMAIN, device_id)},
        name=device_name,
        manufacturer=DEVICE_MANUFACTURER,
        model=DEVICE_MODEL,
    )
