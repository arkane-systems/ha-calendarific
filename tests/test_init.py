"""Tests for config entry setup and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendarific.const import DOMAIN

from .common import entity_id_for, make_entry, setup_entry
from .conftest import FakeApi

import pytest

pytestmark = pytest.mark.usefixtures("frozen_today")


async def test_setup_fetches_current_and_next_year_once(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    """Setting up an instance makes exactly two API calls (this year and next)."""
    await setup_entry(hass, make_entry())
    assert [call["year"] for call in fake_api.calls] == [2026, 2027]
    assert {call["country"] for call in fake_api.calls} == {"US"}


async def test_setup_creates_entities_under_one_device(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    """Holiday sensors, Next Holiday and the calendar all share one device."""
    entry = await setup_entry(hass, make_entry())

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 4  # Halloween, Christmas Day, Next Holiday, calendar
    assert {entity.domain for entity in entities} == {"sensor", "calendar"}

    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, entry.entry_id)}
    assert {entity.device_id for entity in entities} == {devices[0].id}


async def test_two_instances_do_not_collide(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """The same holiday in two instances gets two entities and two devices."""
    first = await setup_entry(hass, make_entry(title="US", country="US"))
    second = await setup_entry(hass, make_entry(title="GB", country="GB"))

    assert entity_id_for(hass, "sensor", first, "halloween") != entity_id_for(
        hass, "sensor", second, "halloween"
    )
    registry = dr.async_get(hass)
    assert len(dr.async_entries_for_config_entry(registry, first.entry_id)) == 1
    assert len(dr.async_entries_for_config_entry(registry, second.entry_id)) == 1


async def test_legacy_entry_is_rejected(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """A pre-0.15 entry (no api_key in its data) fails setup instead of half-loading."""
    entry = MockConfigEntry(domain=DOMAIN, title="Old", data={"name": "Christmas"})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert fake_api.calls == []


async def test_unload_and_reload(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """An entry can be unloaded and set up again without a restart."""
    entry = await setup_entry(hass, make_entry())

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_options_change_reloads_entry(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """Updating the entry's options reloads it, creating the newly added sensor."""
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {}}))
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_christmas_day") is None

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "holidays": {"Halloween": {}, "Christmas Day": {}}}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_christmas_day")
