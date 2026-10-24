"""Shared test helpers and canned Calendarific data."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendarific.const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_DATE_FORMAT,
    CONF_DEFAULTS,
    CONF_HOLIDAYS,
    CONF_ICON_NORMAL,
    CONF_ICON_SOON,
    CONF_ICON_TODAY,
    CONF_SOON,
    CONF_STATE,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
)

# The frozen "now" for tests that use the fake API. Home Assistant's default
# test time zone is US/Pacific, so this is 05:00 on 2026-10-24 locally.
FROZEN_NOW = "2026-10-24 12:00:00+00:00"
TODAY = date(2026, 10, 24)

DEFAULT_SETTINGS: dict[str, Any] = {
    CONF_ICON_NORMAL: "mdi:calendar-blank",
    CONF_ICON_TODAY: "mdi:calendar-star",
    CONF_ICON_SOON: "mdi:calendar",
    CONF_SOON: 3,
    CONF_DATE_FORMAT: "%Y-%m-%d",
    CONF_UNIT_OF_MEASUREMENT: "days",
}

def make_holiday(name: str, when: date, description: str | None = None) -> dict[str, Any]:
    """Build one holiday record in the shape the Calendarific API returns."""
    return {
        "name": name,
        "description": description or f"Description of {name}.",
        "date": {"datetime": {"year": when.year, "month": when.month, "day": when.day}},
    }


def default_holidays_by_year() -> dict[int, list[dict[str, Any]]]:
    """Return a small holiday set for 2026-2028, relative to TODAY (2026-10-24)."""
    names_and_days = [
        ("Independence Day", (7, 4)),  # already passed in 2026
        ("Founders Day", (10, 24)),  # today in 2026
        ("Halloween", (10, 31)),  # 7 days away
        ("Christmas Day", (12, 25)),  # 62 days away
    ]
    return {
        year: [make_holiday(name, date(year, month, day)) for name, (month, day) in names_and_days]
        for year in (2026, 2027, 2028)
    }


def make_entry(
    *,
    title: str = "Test",
    country: str = "US",
    state: str = "",
    api_key: str = "test-key",
    holidays: dict[str, dict[str, Any]] | None = None,
    defaults: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Build a config entry in the current (post-0.15) shape."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        data={CONF_API_KEY: api_key, CONF_COUNTRY: country, CONF_STATE: state},
        options={
            CONF_DEFAULTS: dict(DEFAULT_SETTINGS) if defaults is None else defaults,
            CONF_HOLIDAYS: {"Halloween": {}, "Christmas Day": {}} if holidays is None else holidays,
        },
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add the entry, set it up and wait for it to finish loading."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return an entity's state, failing the test if it has none."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


def entity_id_for(
    hass: HomeAssistant, platform: str, entry: MockConfigEntry, suffix: str
) -> str:
    """Look up an entity of this entry by the suffix of its unique ID."""
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{entry.entry_id}_{suffix}"
    )
    assert entity_id is not None, f"no {platform} entity with unique id suffix {suffix!r}"
    return entity_id


def sensor_id(hass: HomeAssistant, entry: MockConfigEntry, holiday: str) -> str:
    """Look up the sensor entity ID for a tracked holiday."""
    return entity_id_for(hass, "sensor", entry, slugify(holiday))
