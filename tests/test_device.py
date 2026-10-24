"""Tests for the device info shared by an instance's entities."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendarific.const import DOMAIN
from custom_components.calendarific.device import get_device_info

import pytest

from .common import make_entry, setup_entry
from .conftest import FakeApi


def _entry(title: str, country: str = "", state: str = "") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN, title=title, data={"country": country, "state": state}
    )


def test_device_is_a_service_with_a_link_to_the_account() -> None:
    info = get_device_info(_entry("Home"))

    assert info["entry_type"] is DeviceEntryType.SERVICE
    assert info["configuration_url"] == "https://calendarific.com/account"
    assert info["manufacturer"] == "Calendarific"
    assert info["model"] == "Holiday Calendar"


def test_device_is_named_after_the_instance() -> None:
    assert get_device_info(_entry("Home"))["name"] == "Home"


@pytest.mark.parametrize(
    ("country", "state", "name"),
    [("us", "ks", "Calendarific (US - KS)"), ("gb", "", "Calendarific (GB)"), ("", "", "Calendarific")],
)
def test_untitled_instance_falls_back_to_its_location(
    country: str, state: str, name: str
) -> None:
    assert get_device_info(_entry("", country, state))["name"] == name


async def test_registered_device_carries_the_info(hass: HomeAssistant, fake_api: FakeApi) -> None:
    entry = await setup_entry(hass, make_entry(title="Home"))

    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)

    assert device.name == "Home"
    assert device.entry_type is DeviceEntryType.SERVICE
    assert device.configuration_url == "https://calendarific.com/account"
