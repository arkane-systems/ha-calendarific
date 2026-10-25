"""Tests for keeping holiday sensors' friendly names plain."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.calendarific.const import DOMAIN
from custom_components.calendarific.helpers import holiday_unique_id
from custom_components.calendarific.names import async_apply_plain_names

from .common import entity_id_for, get_state, make_entry, sensor_id, setup_entry
from .conftest import FakeApi

pytestmark = pytest.mark.usefixtures("frozen_today", "fake_api")


def _registry_name(hass: HomeAssistant, entity_id: str) -> str | None:
    entry = er.async_get(hass).async_get(entity_id)
    assert entry is not None
    return entry.name


def _friendly(hass: HomeAssistant, entity_id: str) -> str:
    friendly: str = get_state(hass, entity_id).attributes["friendly_name"]
    return friendly


async def _reload(hass: HomeAssistant, entry_id: str) -> None:
    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()


async def test_holiday_sensors_have_a_plain_friendly_name(hass: HomeAssistant) -> None:
    """Exactly the holiday name, on every Home Assistant version."""
    entry = await setup_entry(hass, make_entry(title="Home"))
    entity_id = sensor_id(hass, entry, "Christmas Day")

    assert _registry_name(hass, entity_id) == "Christmas Day"
    assert _friendly(hass, entity_id) == "Christmas Day"


async def test_a_custom_name_is_the_plain_name(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Christmas Day": {"name": "Xmas"}}))
    entity_id = sensor_id(hass, entry, "Christmas Day")

    assert _registry_name(hass, entity_id) == "Xmas"
    assert _friendly(hass, entity_id) == "Xmas"


async def test_next_holiday_and_calendar_keep_their_device_based_names(
    hass: HomeAssistant,
) -> None:
    entry = await setup_entry(hass, make_entry(title="Home"))

    for platform, suffix in (("sensor", "next_holiday"), ("calendar", "calendar")):
        assert _registry_name(hass, entity_id_for(hass, platform, entry, suffix)) is None


async def test_entity_ids_are_not_touched(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    before = sensor_id(hass, entry, "Christmas Day")

    await _reload(hass, entry.entry_id)

    assert sensor_id(hass, entry, "Christmas Day") == before


async def test_entities_registered_by_an_older_version_are_named_on_upgrade(
    hass: HomeAssistant,
) -> None:
    """Version 0.16 registered holiday sensors without a registry name."""
    entry = make_entry(holidays={"Christmas Day": {}})
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        holiday_unique_id(entry.entry_id, "Christmas Day"),
        config_entry=entry,
        original_name="Christmas Day",
    )
    assert old.name is None

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _registry_name(hass, old.entity_id) == "Christmas Day"
    assert _friendly(hass, old.entity_id) == "Christmas Day"


async def test_a_users_own_rename_is_kept(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    entity_id = sensor_id(hass, entry, "Christmas Day")
    er.async_get(hass).async_update_entity(entity_id, name="My Christmas")

    await _reload(hass, entry.entry_id)

    assert _registry_name(hass, entity_id) == "My Christmas"
    assert _friendly(hass, entity_id) == "My Christmas"


async def test_a_users_rename_survives_a_change_of_custom_name(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    entity_id = sensor_id(hass, entry, "Christmas Day")
    er.async_get(hass).async_update_entity(entity_id, name="My Christmas")

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "holidays": {"Christmas Day": {"name": "Xmas"}}}
    )
    await _reload(hass, entry.entry_id)

    assert _registry_name(hass, entity_id) == "My Christmas"


async def test_a_changed_custom_name_follows_through(hass: HomeAssistant) -> None:
    """A name this integration wrote earlier is updated, not mistaken for a rename."""
    entry = await setup_entry(hass, make_entry(holidays={"Christmas Day": {}}))
    entity_id = sensor_id(hass, entry, "Christmas Day")
    assert _registry_name(hass, entity_id) == "Christmas Day"

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "holidays": {"Christmas Day": {"name": "Xmas"}}}
    )
    await _reload(hass, entry.entry_id)

    assert _registry_name(hass, entity_id) == "Xmas"
    assert _friendly(hass, entity_id) == "Xmas"


async def test_clearing_the_name_in_the_ui_restores_it(hass: HomeAssistant) -> None:
    entry = await setup_entry(hass, make_entry())
    entity_id = sensor_id(hass, entry, "Christmas Day")
    er.async_get(hass).async_update_entity(entity_id, name=None)

    await _reload(hass, entry.entry_id)

    assert _registry_name(hass, entity_id) == "Christmas Day"


async def test_only_this_instances_sensors_are_named(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """Two instances with the same holiday each get their own plain name."""
    us = await setup_entry(hass, make_entry(title="US", country="US"))
    gb = await setup_entry(hass, make_entry(title="GB", country="GB"))

    for instance in (us, gb):
        entity_id = sensor_id(hass, instance, "Christmas Day")
        assert _registry_name(hass, entity_id) == "Christmas Day"
        assert _friendly(hass, entity_id) == "Christmas Day"
    assert sensor_id(hass, us, "Christmas Day") != sensor_id(hass, gb, "Christmas Day")


async def test_a_holiday_without_a_registered_entity_is_skipped(hass: HomeAssistant) -> None:
    """If an entity failed to register there is nothing to name, and nothing breaks."""
    entry = await setup_entry(hass, make_entry(holidays={"Christmas Day": {}}))
    registry = er.async_get(hass)
    entity_id = sensor_id(hass, entry, "Christmas Day")
    registry.async_remove(entity_id)

    async_apply_plain_names(hass, entry, {})

    assert registry.async_get(entity_id) is None
