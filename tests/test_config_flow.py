"""Tests for the config flow and options flow."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.calendarific.const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_DEFAULTS,
    CONF_HOLIDAYS,
    CONF_STATE,
    DOMAIN,
)

from .common import API_ERROR, DEFAULT_SETTINGS, make_entry, setup_entry
from .conftest import FakeApi

pytestmark = pytest.mark.usefixtures("frozen_today")


async def _start_user_flow(hass: HomeAssistant, user_input: dict[str, Any]) -> Any:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


async def test_user_flow_creates_entry(hass: HomeAssistant, fake_api: FakeApi) -> None:
    result = await _start_user_flow(
        hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "US", CONF_STATE: "KS"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "defaults"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "holidays"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween", "Christmas Day"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Calendarific (US - KS)"
    assert result["data"] == {CONF_API_KEY: "secret", CONF_COUNTRY: "US", CONF_STATE: "KS"}
    assert result["options"] == {
        CONF_DEFAULTS: DEFAULT_SETTINGS,
        CONF_HOLIDAYS: {"Halloween": {}, "Christmas Day": {}},
    }


async def test_user_flow_uses_custom_name_as_title(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    result = await _start_user_flow(
        hass, {"name": "Home holidays", CONF_API_KEY: "secret", CONF_COUNTRY: "GB"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween"]}
    )
    await hass.async_block_till_done()

    assert result["title"] == "Home holidays"
    assert result["data"][CONF_STATE] == ""


async def test_user_flow_without_state_titles_by_country(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    result = await _start_user_flow(hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "gb"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween"]}
    )
    await hass.async_block_till_done()

    assert result["title"] == "Calendarific (GB)"


async def test_user_flow_errors_when_no_holidays_found(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    fake_api.holidays_by_year = {}
    result = await _start_user_flow(hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "ZZ"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_holidays_found"}


async def test_user_flow_errors_when_api_rejects_key(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    fake_api.error = API_ERROR
    result = await _start_user_flow(hass, {CONF_API_KEY: "bad", CONF_COUNTRY: "US"})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_holidays_found"}


async def test_user_flow_recovers_after_error(hass: HomeAssistant, fake_api: FakeApi) -> None:
    fake_api.error = API_ERROR
    result = await _start_user_flow(hass, {CONF_API_KEY: "bad", CONF_COUNTRY: "US"})
    assert result["errors"] == {"base": "no_holidays_found"}

    fake_api.error = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "good", CONF_COUNTRY: "US"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "defaults"


async def test_holidays_step_requires_a_selection(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    result = await _start_user_flow(hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "US"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "holidays"
    assert result["errors"] == {"base": "no_holidays_selected"}


# -- options flow ---------------------------------------------------------------


async def _open_options(hass: HomeAssistant, entry_id: str, action: str) -> Any:
    result = await hass.config_entries.options.async_init(entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"action": action}
    )


async def test_options_add_holiday_keeps_existing_overrides(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {"icon_normal": "mdi:pumpkin"}})
    )

    result = await _open_options(hass, entry.entry_id, "holidays")
    assert result["step_id"] == "holidays"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween", "Christmas Day"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HOLIDAYS] == {
        "Halloween": {"icon_normal": "mdi:pumpkin"},
        "Christmas Day": {},
    }
    assert entry.options[CONF_DEFAULTS] == DEFAULT_SETTINGS


async def test_options_remove_holiday_discards_its_override(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(
        hass,
        make_entry(holidays={"Halloween": {"name": "Spooky"}, "Christmas Day": {}}),
    )

    result = await _open_options(hass, entry.entry_id, "holidays")
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Christmas Day"]}
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HOLIDAYS] == {"Christmas Day": {}}


async def test_options_holidays_requires_a_selection(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())

    result = await _open_options(hass, entry.entry_id, "holidays")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_holidays_selected"}


async def test_options_edit_defaults_keeps_holidays(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())
    new_defaults = {**DEFAULT_SETTINGS, "icon_normal": "mdi:star", "days_as_soon": 5}

    result = await _open_options(hass, entry.entry_id, "defaults")
    assert result["step_id"] == "defaults"
    await hass.config_entries.options.async_configure(result["flow_id"], new_defaults)
    await hass.async_block_till_done()

    assert entry.options[CONF_DEFAULTS] == new_defaults
    assert entry.options[CONF_HOLIDAYS] == {"Halloween": {}, "Christmas Day": {}}


async def test_options_customize_stores_only_differences(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())

    result = await _open_options(hass, entry.entry_id, "customize")
    assert result["step_id"] == "customize"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"holiday": "Halloween"}
    )
    assert result["step_id"] == "customize_values"
    assert result["description_placeholders"] == {"holiday": "Halloween"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_SETTINGS, "name": "  Spooky Day ", "icon_normal": "mdi:pumpkin"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HOLIDAYS]["Halloween"] == {
        "name": "Spooky Day",
        "icon_normal": "mdi:pumpkin",
    }
    assert entry.options[CONF_HOLIDAYS]["Christmas Day"] == {}


async def test_options_customize_matching_defaults_clears_override(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {"icon_normal": "mdi:pumpkin"}})
    )

    result = await _open_options(hass, entry.entry_id, "customize")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"holiday": "Halloween"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"], {**DEFAULT_SETTINGS, "name": ""}
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HOLIDAYS]["Halloween"] == {}


async def test_options_customize_reset_ignores_other_fields(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(
        hass, make_entry(holidays={"Halloween": {"name": "Spooky", "days_as_soon": 9}})
    )

    result = await _open_options(hass, entry.entry_id, "customize")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"holiday": "Halloween"}
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**DEFAULT_SETTINGS, "name": "Ignored", "icon_normal": "mdi:ignored", "reset_to_default": True},
    )
    await hass.async_block_till_done()

    assert entry.options[CONF_HOLIDAYS]["Halloween"] == {}


async def test_options_customize_aborts_without_holidays(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={}))

    result = await _open_options(hass, entry.entry_id, "customize")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_holidays_configured"
