"""Tests for the config flow and options flow."""

from __future__ import annotations

from typing import Any

from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
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

from .common import DEFAULT_SETTINGS, get_state, make_entry, sensor_id, setup_entry
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


@pytest.mark.parametrize(
    ("break_api", "error"),
    [
        (lambda api: api.fail(401, "Invalid API key."), "invalid_auth"),
        (lambda api: api.fail(403, "Subscription expired."), "invalid_auth"),
        (lambda api: api.fail(429, "Limit reached."), "rate_limited"),
        (lambda api: api.fail(500, "Down."), "cannot_connect"),
        (lambda api: api.raise_error(ClientError()), "cannot_connect"),
        (lambda api: api.raise_error(TimeoutError()), "cannot_connect"),
    ],
)
async def test_user_flow_reports_why_the_api_failed(
    hass: HomeAssistant, fake_api: FakeApi, break_api: Any, error: str
) -> None:
    break_api(fake_api)
    result = await _start_user_flow(hass, {CONF_API_KEY: "bad", CONF_COUNTRY: "US"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}


async def test_user_flow_recovers_after_error(hass: HomeAssistant, fake_api: FakeApi) -> None:
    fake_api.fail(401, "Invalid API key.")
    result = await _start_user_flow(hass, {CONF_API_KEY: "bad", CONF_COUNTRY: "US"})
    assert result["errors"] == {"base": "invalid_auth"}

    fake_api.recover()
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
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == ["holidays", "defaults", "customize"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": action}
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


@pytest.mark.parametrize(
    ("status", "reason"), [(401, "invalid_auth"), (429, "rate_limited"), (500, "cannot_connect")]
)
async def test_options_holidays_aborts_when_the_api_fails(
    hass: HomeAssistant, fake_api: FakeApi, status: int, reason: str
) -> None:
    entry = await setup_entry(hass, make_entry())
    fake_api.fail(status)

    result = await _open_options(hass, entry.entry_id, "holidays")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


# -- reauth flow ----------------------------------------------------------------


async def _entry_needing_reauth(hass: HomeAssistant, fake_api: FakeApi) -> Any:
    """Set up an entry whose key the API rejects, leaving a reauth flow in progress."""
    fake_api.fail(401, "Invalid API key.")
    entry = make_entry(api_key="revoked")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    return entry


async def test_reauth_updates_the_key_and_reloads(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await _entry_needing_reauth(hass, fake_api)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == config_entries.SOURCE_REAUTH

    result = await hass.config_entries.flow.async_configure(flow["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    fake_api.recover()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "renewed"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "renewed"
    assert entry.state is ConfigEntryState.LOADED
    assert fake_api.calls[-1]["api_key"] == "renewed"


async def test_reauth_rejects_a_bad_replacement_key(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await _entry_needing_reauth(hass, fake_api)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_API_KEY: "still-bad"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_API_KEY] == "revoked"


async def test_reauth_reports_connection_problems(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    await _entry_needing_reauth(hass, fake_api)
    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    fake_api.fail(500)
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {CONF_API_KEY: "renewed"}
    )

    assert result["errors"] == {"base": "cannot_connect"}


# -- unique config entries ------------------------------------------------------


async def test_created_entry_has_a_unique_id_and_current_schema_version(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    result = await _start_user_flow(
        hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "US", CONF_STATE: "KS"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween"]}
    )
    await hass.async_block_till_done()

    entry = result["result"]
    assert entry.unique_id == "us-ks"
    assert (entry.version, entry.minor_version) == (1, 2)


async def test_user_flow_strips_whitespace(hass: HomeAssistant, fake_api: FakeApi) -> None:
    result = await _start_user_flow(
        hass, {CONF_API_KEY: "secret", CONF_COUNTRY: " us ", CONF_STATE: " ks "}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], dict(DEFAULT_SETTINGS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Halloween"]}
    )
    await hass.async_block_till_done()

    assert result["data"][CONF_COUNTRY] == "us"
    assert result["data"][CONF_STATE] == "ks"


@pytest.mark.parametrize("country", ["US", "us", " Us "])
async def test_same_country_and_state_cannot_be_added_twice(
    hass: HomeAssistant, fake_api: FakeApi, country: str
) -> None:
    await setup_entry(hass, make_entry(country="US", state="KS"))
    calls = len(fake_api.calls)

    result = await _start_user_flow(
        hass, {CONF_API_KEY: "other", CONF_COUNTRY: country, CONF_STATE: "ks"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(fake_api.calls) == calls  # rejected before spending any quota


async def test_another_state_of_the_same_country_is_allowed(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    await setup_entry(hass, make_entry(country="US", state="KS"))

    result = await _start_user_flow(
        hass, {CONF_API_KEY: "secret", CONF_COUNTRY: "US", CONF_STATE: "MO"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "defaults"


# -- reconfigure flow -----------------------------------------------------------


async def test_reconfigure_with_a_new_key_keeps_the_place(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(country="US", state="KS", api_key="old"))

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new", CONF_COUNTRY: "US", CONF_STATE: "KS"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_KEY] == "new"
    assert entry.unique_id == "us-ks"
    assert entry.state is ConfigEntryState.LOADED
    assert fake_api.calls[-1]["api_key"] == "new"


async def test_reconfigure_treats_a_case_change_as_the_same_place(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(country="US", state="KS"))

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key", CONF_COUNTRY: "us ", CONF_STATE: "ks"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_COUNTRY] == "us"
    assert entry.options[CONF_HOLIDAYS] == {"Halloween": {}, "Christmas Day": {}}


async def _move_to_gb(hass: HomeAssistant, entry: Any) -> Any:
    result = await entry.start_reconfigure_flow(hass)
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-key", CONF_COUNTRY: "GB", CONF_STATE: ""}
    )


async def test_moving_to_another_country_repicks_holidays_and_keeps_customizations(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(
        hass,
        make_entry(
            title="Calendarific (US)",
            holidays={"Halloween": {"name": "Spooky"}, "Christmas Day": {"icon_normal": "mdi:tree"}},
        ),
    )
    # Halloween isn't offered in the new place; Christmas Day is.
    for year, holidays in fake_api.holidays_by_year.items():
        fake_api.holidays_by_year[year] = [h for h in holidays if h["name"] != "Halloween"]

    result = await _move_to_gb(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_holidays"
    assert result["data_schema"]({})[CONF_HOLIDAYS] == ["Christmas Day"]  # carried over

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Christmas Day", "Founders Day"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "gb"
    assert entry.data[CONF_COUNTRY] == "GB"
    assert entry.title == "Calendarific (GB)"  # followed the place: it was never renamed
    assert entry.options[CONF_HOLIDAYS] == {
        "Christmas Day": {"icon_normal": "mdi:tree"},  # customization kept
        "Founders Day": {},
    }
    assert entry.options[CONF_DEFAULTS] == DEFAULT_SETTINGS
    assert entry.state is ConfigEntryState.LOADED
    assert fake_api.calls[-1]["country"] == "GB"  # refetched for the new place
    assert get_state(hass, sensor_id(hass, entry, "Christmas Day")).state == "62"


async def test_moving_keeps_a_title_the_user_chose(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(title="Home holidays"))

    result = await _move_to_gb(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: ["Christmas Day"]}
    )
    await hass.async_block_till_done()

    assert entry.title == "Home holidays"
    assert entry.unique_id == "gb"


async def test_moving_requires_at_least_one_holiday(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())

    result = await _move_to_gb(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOLIDAYS: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_holidays_selected"}
    assert entry.data[CONF_COUNTRY] == "US"  # nothing changed


async def test_cannot_move_onto_a_place_another_instance_tracks(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    await setup_entry(hass, make_entry(title="UK", country="GB"))
    entry = await setup_entry(hass, make_entry(title="US", country="US"))
    calls = len(fake_api.calls)

    result = await _move_to_gb(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "already_configured"}
    assert len(fake_api.calls) == calls


@pytest.mark.parametrize(
    ("break_api", "error"),
    [
        (lambda api: api.fail(401), "invalid_auth"),
        (lambda api: api.fail(429), "rate_limited"),
        (lambda api: api.raise_error(ClientError()), "cannot_connect"),
    ],
)
async def test_reconfigure_reports_why_the_api_failed(
    hass: HomeAssistant, fake_api: FakeApi, break_api: Any, error: str
) -> None:
    entry = await setup_entry(hass, make_entry())
    break_api(fake_api)

    result = await _move_to_gb(hass, entry)

    assert result["errors"] == {"base": error}
    assert entry.data[CONF_COUNTRY] == "US"


async def test_reconfigure_errors_when_the_new_place_has_no_holidays(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry())
    fake_api.holidays_by_year = {}

    result = await _move_to_gb(hass, entry)

    assert result["errors"] == {"base": "no_holidays_found"}
