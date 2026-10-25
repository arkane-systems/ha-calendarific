"""Tests for the holiday and Next Holiday sensors."""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from .common import TODAY, entity_id_for, get_state, make_entry, sensor_id, setup_entry

pytestmark = pytest.mark.usefixtures("frozen_today", "fake_api")


def _registered_name(hass: HomeAssistant, entity_id: str) -> str | None:
    """The name the entity registered with, which the frontend displays."""
    entry = er.async_get(hass).async_get(entity_id)
    assert entry is not None
    return entry.original_name


def _friendly_name(hass: HomeAssistant, entity_id: str) -> str:
    friendly_name: str = get_state(hass, entity_id).attributes["friendly_name"]
    return friendly_name


async def test_state_is_days_remaining_with_attributes(hass: HomeAssistant) -> None:
    """The state is the whole days until the next occurrence."""
    entry = await setup_entry(hass, make_entry())
    state = get_state(hass, sensor_id(hass, entry, "Christmas Day"))

    assert state.state == str((date(2026, 12, 25) - TODAY).days)
    assert state.attributes["date"] == "2026-12-25"
    assert state.attributes["description"] == "Description of Christmas Day."
    assert state.attributes["attribution"] == "Data provided by calendarific.com"
    assert state.attributes["unit_of_measurement"] == "d"
    assert state.attributes["device_class"] == "duration"
    assert state.attributes["icon"] == "mdi:calendar-blank"


async def test_holiday_today_is_zero_with_today_icon(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Founders Day": {}}))
    state = get_state(hass, sensor_id(hass, entry, "Founders Day"))

    assert state.state == "0"
    assert state.attributes["icon"] == "mdi:calendar-star"


async def test_passed_holiday_rolls_over_to_next_year(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Independence Day": {}}))
    state = get_state(hass, sensor_id(hass, entry, "Independence Day"))

    assert state.state == str((date(2027, 7, 4) - TODAY).days)
    assert state.attributes["date"] == "2027-07-04"


async def test_icon_switches_to_soon_within_threshold(hass: HomeAssistant) -> None:
    """Halloween is 7 days out: normal by default, 'soon' once the threshold is raised."""
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {}, "Christmas Day": {"days_as_soon": 10}})
    )
    assert get_state(hass, sensor_id(hass, entry, "Halloween")).attributes["icon"] == (
        "mdi:calendar-blank"
    )

    entry2 = await setup_entry(
        hass, make_entry(title="Second", state="KS", holidays={"Halloween": {"days_as_soon": 10}})
    )
    assert get_state(hass, sensor_id(hass, entry2, "Halloween")).attributes["icon"] == (
        "mdi:calendar"
    )


async def test_unknown_when_holiday_missing_from_api_data(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Nonexistent Day": {}}))
    state = get_state(hass, sensor_id(hass, entry, "Nonexistent Day"))

    assert state.state == "unknown"
    assert state.attributes["date"] is None
    assert state.attributes["description"] is None
    assert state.attributes["icon"] == "mdi:calendar-blank"


async def test_instance_defaults_apply_and_overrides_win(hass: HomeAssistant) -> None:
    defaults = {
        "icon_normal": "mdi:star",
        "icon_today": "mdi:star-circle",
        "icon_soon": "mdi:star-half",
        "days_as_soon": 3,
        "date_format": "%d/%m/%Y",
    }
    entry = await setup_entry(
        hass,
        make_entry(
            defaults=defaults,
            holidays={"Halloween": {}, "Christmas Day": {"icon_normal": "mdi:tree"}},
        ),
    )
    halloween = get_state(hass, sensor_id(hass, entry, "Halloween"))
    assert halloween.attributes["icon"] == "mdi:star"
    assert halloween.attributes["date"] == "31/10/2026"

    christmas = get_state(hass, sensor_id(hass, entry, "Christmas Day"))
    assert christmas.attributes["icon"] == "mdi:tree"
    assert christmas.attributes["date"] == "25/12/2026"


async def test_custom_name_changes_friendly_name_only(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Christmas Day": {"name": "Xmas"}}))
    entity_id = sensor_id(hass, entry, "Christmas Day")

    assert _registered_name(hass, entity_id) == "Xmas"
    assert _friendly_name(hass, entity_id) == "Xmas"


async def test_next_holiday_reports_soonest_tracked_holiday(hass: HomeAssistant) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Christmas Day": {}, "Halloween": {}, "Independence Day": {}})
    )
    state = get_state(hass, entity_id_for(hass, "sensor", entry, "next_holiday"))

    assert state.state == "Halloween"
    assert state.attributes["days"] == (date(2026, 10, 31) - TODAY).days


async def test_next_holiday_uses_custom_name(hass: HomeAssistant) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {"name": "Spooky Day"}, "Christmas Day": {}})
    )
    state = get_state(hass, entity_id_for(hass, "sensor", entry, "next_holiday"))
    assert state.state == "Spooky Day"


async def test_next_holiday_unknown_without_matches(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Nonexistent Day": {}}))
    state = get_state(hass, entity_id_for(hass, "sensor", entry, "next_holiday"))

    assert state.state == "unknown"
    assert state.attributes["days"] is None


async def test_holiday_sensors_are_named_after_the_holiday_alone(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(title="Home"))
    entity_id = sensor_id(hass, entry, "Christmas Day")

    assert _registered_name(hass, entity_id) == "Christmas Day"
    assert _friendly_name(hass, entity_id) == "Christmas Day"


async def test_next_holiday_is_prefixed_with_its_instance(hass: HomeAssistant) -> None:
    """Several instances' Next Holiday sensors can be told apart by name."""
    us = await setup_entry(hass, make_entry(title="US", country="US"))
    gb = await setup_entry(hass, make_entry(title="GB", country="GB"))

    assert get_state(hass, entity_id_for(hass, "sensor", us, "next_holiday")).attributes[
        "friendly_name"
    ] == "US Next holiday"
    assert get_state(hass, entity_id_for(hass, "sensor", gb, "next_holiday")).attributes[
        "friendly_name"
    ] == "GB Next holiday"


async def test_calendar_takes_the_instance_name(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(title="Home"))

    state = get_state(hass, entity_id_for(hass, "calendar", entry, "calendar"))
    assert state.attributes["friendly_name"] == "Home"
