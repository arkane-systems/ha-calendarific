"""Tests for the per-instance calendar entity."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from .common import entity_id_for, get_state, make_entry, setup_entry

pytestmark = pytest.mark.usefixtures("frozen_today", "fake_api")


async def _events(
    hass: HomeAssistant, entity_id: str, start: date, end: date
) -> list[dict[str, Any]]:
    """Fetch calendar events for [start, end] through the public service."""
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": f"{start.isoformat()} 00:00:00",
            "end_date_time": f"{end.isoformat()} 23:59:59",
        },
        blocking=True,
        return_response=True,
    )
    assert response is not None
    events: list[dict[str, Any]] = response[entity_id]["events"]
    return events


async def test_calendar_lists_tracked_holidays_in_range(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    entity_id = entity_id_for(hass, "calendar", entry, "calendar")

    events = await _events(hass, entity_id, date(2026, 10, 1), date(2026, 12, 31))

    assert sorted(event["summary"] for event in events) == ["Christmas Day", "Halloween"]
    halloween = next(event for event in events if event["summary"] == "Halloween")
    assert halloween["start"] == "2026-10-31"
    assert halloween["end"] == "2026-11-01"
    assert halloween["description"] == "Description of Halloween."


async def test_calendar_excludes_holidays_outside_range(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    entity_id = entity_id_for(hass, "calendar", entry, "calendar")

    events = await _events(hass, entity_id, date(2026, 11, 1), date(2026, 12, 31))

    assert [event["summary"] for event in events] == ["Christmas Day"]


async def test_calendar_uses_sensor_custom_names(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {"name": "Spooky Day"}}))
    entity_id = entity_id_for(hass, "calendar", entry, "calendar")

    events = await _events(hass, entity_id, date(2026, 10, 1), date(2026, 12, 31))

    assert [event["summary"] for event in events] == ["Spooky Day"]


async def test_calendar_event_is_the_soonest_upcoming_holiday(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    state = get_state(hass, entity_id_for(hass, "calendar", entry, "calendar"))

    assert state.attributes["message"] == "Halloween"


async def test_calendar_shows_holidays_already_passed_this_year(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Independence Day": {}}))
    entity_id = entity_id_for(hass, "calendar", entry, "calendar")

    events = await _events(hass, entity_id, date(2026, 7, 1), date(2026, 7, 31))

    assert [event["summary"] for event in events] == ["Independence Day"]


async def test_calendar_range_end_is_exclusive(hass: HomeAssistant) -> None:
    """A range ending at midnight on a holiday's date does not include that holiday."""
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {}}))
    entity_id = entity_id_for(hass, "calendar", entry, "calendar")

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": entity_id,
            "start_date_time": "2026-10-30 00:00:00",
            "end_date_time": "2026-10-31 00:00:00",
        },
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert response[entity_id]["events"] == []


async def test_calendar_event_is_today_s_holiday_when_there_is_one(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Founders Day": {}, "Halloween": {}}))
    state = get_state(hass, entity_id_for(hass, "calendar", entry, "calendar"))

    assert state.state == "on"
    assert state.attributes["message"] == "Founders Day"
