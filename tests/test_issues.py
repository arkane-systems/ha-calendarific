"""Tests for the repair issue raised when a tracked holiday disappears."""

from __future__ import annotations

from datetime import date, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.calendarific.const import DOMAIN
from custom_components.calendarific.coordinator import REFRESH_INTERVAL
from custom_components.calendarific.issues import holiday_missing_issue_id

from .common import entity_id_for, make_entry, make_holiday, setup_entry
from .conftest import FakeApi

pytestmark = pytest.mark.usefixtures("frozen_today")


def _issue(hass: HomeAssistant, entry_id: str, holiday: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, holiday_missing_issue_id(entry_id, holiday))


async def test_an_unlisted_holiday_raises_a_fixable_issue(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(title="Home", holidays={"Halloween": {}, "Boxing Day": {}}))

    issue = _issue(hass, entry.entry_id, "Boxing Day")
    assert issue is not None
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == "holiday_missing"
    assert issue.translation_placeholders == {"holiday": "Boxing Day", "title": "Home"}
    assert _issue(hass, entry.entry_id, "Halloween") is None


async def test_a_listed_holiday_with_no_upcoming_date_is_not_an_issue(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    """Passed this year and absent next year: unknown for now, but Calendarific knows it."""
    fake_api.holidays_by_year[2027] = []
    entry = await setup_entry(hass, make_entry(holidays={"Independence Day": {}}))

    assert _issue(hass, entry.entry_id, "Independence Day") is None


async def test_the_issue_clears_when_calendarific_lists_the_holiday_again(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Boxing Day": {}}))
    assert _issue(hass, entry.entry_id, "Boxing Day") is not None

    for year in (2026, 2027):
        fake_api.holidays_by_year[year].append(make_holiday("Boxing Day", date(year, 12, 26)))
    frozen_today.tick(REFRESH_INTERVAL + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _issue(hass, entry.entry_id, "Boxing Day") is None


async def test_an_outage_neither_raises_nor_clears_issues(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Boxing Day": {}}))
    fake_api.fail(500)

    frozen_today.tick(REFRESH_INTERVAL + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert _issue(hass, entry.entry_id, "Boxing Day") is not None


async def test_issues_of_untracked_holidays_are_cleared_on_reload(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {}, "Boxing Day": {}}))
    assert _issue(hass, entry.entry_id, "Boxing Day") is not None

    hass.config_entries.async_update_entry(entry, options={**entry.options, "holidays": {"Halloween": {}}})
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, entry.entry_id, "Boxing Day") is None


async def test_removing_the_instance_clears_its_issues(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Boxing Day": {}}))
    other = await setup_entry(hass, make_entry(title="GB", country="GB", holidays={"Boxing Day": {}}))

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert _issue(hass, entry.entry_id, "Boxing Day") is None
    assert _issue(hass, other.entry_id, "Boxing Day") is not None  # not touched


async def test_fix_flow_stops_tracking_the_holiday(
    hass: HomeAssistant, fake_api: FakeApi, hass_client: ClientSessionGenerator
) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {"name": "Spooky"}, "Boxing Day": {}})
    )
    boxing_day = entity_id_for(hass, "sensor", entry, "boxing_day")
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    issue_id = holiday_missing_issue_id(entry.entry_id, "Boxing Day")

    response = await client.post(
        "/api/repairs/issues/fix", json={"handler": DOMAIN, "issue_id": issue_id}
    )
    flow = await response.json()
    assert flow["step_id"] == "confirm"
    assert flow["description_placeholders"] == {"holiday": "Boxing Day"}

    response = await client.post(f"/api/repairs/issues/fix/{flow['flow_id']}", json={})
    assert (await response.json())["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.options["holidays"] == {"Halloween": {"name": "Spooky"}}
    assert _issue(hass, entry.entry_id, "Boxing Day") is None
    assert er.async_get(hass).async_get(boxing_day) is None  # its sensor was cleaned up
