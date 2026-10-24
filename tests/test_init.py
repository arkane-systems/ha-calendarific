"""Tests for config entry setup and unload."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.calendarific.const import DOMAIN
from custom_components.calendarific.coordinator import CalendarificCoordinator

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


async def test_options_flow_reloads_entry(hass: HomeAssistant, fake_api: FakeApi) -> None:
    """Saving options through the flow reloads the entry, creating the added sensor."""
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {}}))
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_christmas_day") is None

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "holidays"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"holidays": ["Halloween", "Christmas Day"]}
    )
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_christmas_day")


async def test_runtime_data_holds_the_coordinator(hass: HomeAssistant, fake_api: FakeApi) -> None:
    entry = await setup_entry(hass, make_entry())
    assert isinstance(entry.runtime_data, CalendarificCoordinator)


# -- config entry migration -----------------------------------------------------


def _old_entry(**kwargs: object) -> MockConfigEntry:
    """An entry as created before unique IDs existed (minor version 1)."""
    entry = make_entry(**kwargs)  # type: ignore[arg-type]
    return MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        data=entry.data,
        options=entry.options,
        version=1,
        minor_version=1,
        unique_id=None,
    )


async def test_migration_gives_existing_entries_a_unique_id(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = _old_entry(country="US", state="KS")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == "us-ks"
    assert entry.minor_version == 3


async def test_migration_leaves_a_duplicate_instance_without_an_id_but_working(
    hass: HomeAssistant, fake_api: FakeApi, caplog: pytest.LogCaptureFixture
) -> None:
    first = _old_entry(title="First", country="US", state="KS")
    second = _old_entry(title="Second", country="US", state="KS")
    first.add_to_hass(hass)
    second.add_to_hass(hass)

    # Setting up the integration sets up (and migrates) every entry, in order.
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()

    assert first.unique_id == "us-ks"
    assert second.unique_id is None
    assert second.minor_version == 3
    assert second.state is ConfigEntryState.LOADED
    assert "duplicates another instance" in caplog.text


async def test_migration_of_a_legacy_entry_still_reports_it_as_incompatible(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Old", data={"name": "Christmas"})
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.unique_id is None
    assert entry.error_reason_translation_key == "legacy_entry"


async def test_entry_from_a_newer_major_version_is_not_loaded(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, title="Future", data=make_entry().data, version=2, minor_version=0
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_entry_from_a_newer_minor_version_still_loads(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    template = make_entry()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=template.title,
        data=template.data,
        options=template.options,
        unique_id=template.unique_id,
        minor_version=3,
    )
    await setup_entry(hass, entry)
    assert entry.minor_version == 3


# -- stale entities ---------------------------------------------------------------


async def test_deselecting_a_holiday_removes_its_entity(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())
    registry = er.async_get(hass)
    christmas = entity_id_for(hass, "sensor", entry, "christmas_day")
    halloween = entity_id_for(hass, "sensor", entry, "halloween")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "holidays"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"holidays": ["Halloween"]}
    )
    await hass.async_block_till_done()

    assert registry.async_get(christmas) is None
    assert hass.states.get(christmas) is None
    assert registry.async_get(halloween) is not None
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 3


async def test_stale_cleanup_leaves_other_instances_alone(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    mine = await setup_entry(hass, make_entry(title="US", country="US", holidays={"Halloween": {}}))
    theirs = await setup_entry(hass, make_entry(title="GB", country="GB"))
    registry = er.async_get(hass)
    before = len(er.async_entries_for_config_entry(registry, theirs.entry_id))

    hass.config_entries.async_update_entry(
        mine, options={**mine.options, "holidays": {}}
    )
    await hass.config_entries.async_reload(mine.entry_id)
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(registry, theirs.entry_id)) == before
    assert len(er.async_entries_for_config_entry(registry, mine.entry_id)) == 2  # next + calendar


async def test_renaming_a_holiday_sensor_does_not_make_it_stale(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {"name": "Spooky"}}))
    entity_id = entity_id_for(hass, "sensor", entry, "halloween")

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert er.async_get(hass).async_get(entity_id) is not None


# -- migration to minor 3 -----------------------------------------------------------


async def test_migration_drops_the_unit_setting(hass: HomeAssistant, fake_api: FakeApi) -> None:
    defaults = {"icon_normal": "mdi:star", "days_as_soon": 3, "unit_of_measurement": "dias"}
    entry = _old_entry(
        defaults=defaults,
        holidays={
            "Halloween": {"unit_of_measurement": "d", "icon_today": "mdi:pumpkin"},
            "Christmas Day": {},
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.options["defaults"] == {"icon_normal": "mdi:star", "days_as_soon": 3}
    assert entry.options["holidays"] == {
        "Halloween": {"icon_today": "mdi:pumpkin"},
        "Christmas Day": {},
    }


async def test_migration_from_minor_two_only_drops_the_unit(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    template = make_entry(defaults={"icon_normal": "mdi:star", "unit_of_measurement": "dias"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=template.title,
        data=template.data,
        options=template.options,
        unique_id="us",
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "us"
    assert entry.options["defaults"] == {"icon_normal": "mdi:star"}


async def test_migration_copes_with_entries_that_have_no_options(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Bare",
        data=make_entry().data,
        unique_id="us",
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 3
