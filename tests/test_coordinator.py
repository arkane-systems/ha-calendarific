"""Tests for the coordinator: refresh cadence, outages, auth failures, rollover."""

from __future__ import annotations

from datetime import date, timedelta
import logging

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.calendarific.const import DOMAIN
from custom_components.calendarific.coordinator import REFRESH_INTERVAL, RETRY_INTERVAL

from .common import get_state, make_entry, sensor_id, setup_entry
from .conftest import FakeApi

pytestmark = pytest.mark.usefixtures("frozen_today")

COORDINATOR_LOGGER = "custom_components.calendarific.coordinator"


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta) -> None:
    """Move time forward, fire due timers and let everything settle."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


# -- setup outcomes -------------------------------------------------------------


@pytest.mark.parametrize(
    ("break_api", "state"),
    [
        (lambda api: api.raise_error(ClientError()), ConfigEntryState.SETUP_RETRY),
        (lambda api: api.raise_error(TimeoutError()), ConfigEntryState.SETUP_RETRY),
        (lambda api: api.fail(500), ConfigEntryState.SETUP_RETRY),
        (lambda api: api.fail(429, "Limit reached."), ConfigEntryState.SETUP_RETRY),
        (lambda api: api.fail(401, "Invalid API key."), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_first_refresh_failures(
    hass: HomeAssistant, fake_api: FakeApi, break_api: object, state: ConfigEntryState
) -> None:
    """Transient failures retry setup; a rejected key fails it and starts reauth."""
    break_api(fake_api)  # type: ignore[operator]
    entry = make_entry()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is state
    if state is ConfigEntryState.SETUP_ERROR:
        assert entry.error_reason_translation_key == "auth_failed"
        assert entry.error_reason_translation_placeholders == {"detail": "Invalid API key."}
    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_REAUTH
    ]
    assert len(reauth_flows) == (1 if state is ConfigEntryState.SETUP_ERROR else 0)


async def test_a_failed_first_year_does_not_request_the_second(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    """Failures stop at once: every request counts against the monthly quota."""
    fake_api.fail(500)
    entry = make_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert [call["year"] for call in fake_api.calls] == [2026]


# -- refresh cadence and midnight rollover -------------------------------------


async def test_midnight_rolls_day_counts_over_without_an_api_call(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    entry = await setup_entry(hass, make_entry())
    halloween = sensor_id(hass, entry, "Halloween")
    assert get_state(hass, halloween).state == "7"
    calls = len(fake_api.calls)

    # FROZEN_NOW is 05:00 US/Pacific; 19 hours later it is 00:00 the next day.
    await _advance(hass, frozen_today, timedelta(hours=19, seconds=1))

    assert get_state(hass, halloween).state == "6"
    assert len(fake_api.calls) == calls


async def test_sensors_do_not_poll(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    """Entities only react to the coordinator, so a quiet hour makes no requests."""
    await setup_entry(hass, make_entry())
    calls = len(fake_api.calls)

    await _advance(hass, frozen_today, timedelta(hours=1))

    assert len(fake_api.calls) == calls


async def test_holidays_are_refetched_daily(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    await setup_entry(hass, make_entry())

    await _advance(hass, frozen_today, REFRESH_INTERVAL + timedelta(minutes=1))

    assert [call["year"] for call in fake_api.calls] == [2026, 2027, 2026, 2027]


async def test_new_year_refetches_for_the_new_pair_of_years(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    frozen_today.move_to("2026-12-31 18:00:00+00:00")  # 10:00 US/Pacific
    entry = await setup_entry(hass, make_entry())
    halloween = sensor_id(hass, entry, "Halloween")
    assert [call["year"] for call in fake_api.calls] == [2026, 2027]

    # Local midnight is 08:00 UTC; the tick must fetch 2027 and 2028.
    await _advance(hass, frozen_today, timedelta(hours=14))

    assert [call["year"] for call in fake_api.calls[2:]] == [2027, 2028]
    assert set(entry.runtime_data.data.by_year) == {2027, 2028}
    assert get_state(hass, halloween).state == str((date(2027, 10, 31) - date(2027, 1, 1)).days)


# -- outages ----------------------------------------------------------------------


async def test_outage_keeps_serving_cached_data_and_logs_once(
    hass: HomeAssistant,
    fake_api: FakeApi,
    frozen_today: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=COORDINATOR_LOGGER)
    entry = await setup_entry(hass, make_entry())
    coordinator = entry.runtime_data
    halloween = sensor_id(hass, entry, "Halloween")

    fake_api.fail(500, "Down for maintenance.")
    await _advance(hass, frozen_today, REFRESH_INTERVAL + timedelta(minutes=1))

    assert get_state(hass, halloween).state == "6"  # a day closer, still available
    assert coordinator.update_interval == RETRY_INTERVAL
    warnings = [
        r for r in caplog.records if r.levelno == logging.WARNING and "cached data" in r.message
    ]
    assert len(warnings) == 1
    assert "Down for maintenance." in warnings[0].message

    # Retries keep failing quietly...
    await _advance(hass, frozen_today, RETRY_INTERVAL + timedelta(minutes=1))
    await _advance(hass, frozen_today, RETRY_INTERVAL + timedelta(minutes=1))
    assert get_state(hass, halloween).state == "6"
    noisy = [
        r for r in caplog.records if r.levelno >= logging.WARNING and r.name == COORDINATOR_LOGGER
    ]
    assert len(noisy) == 1

    # ...until the API comes back.
    fake_api.recover()
    await _advance(hass, frozen_today, RETRY_INTERVAL + timedelta(minutes=1))

    assert coordinator.update_interval == REFRESH_INTERVAL
    assert any("reachable again" in r.message for r in caplog.records)


async def test_failed_refresh_waits_the_retry_interval_before_trying_again(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    """A failed refresh costs one request, then nothing until RETRY_INTERVAL has passed."""
    await setup_entry(hass, make_entry())
    fake_api.fail(500)
    before = len(fake_api.calls)

    await _advance(hass, frozen_today, REFRESH_INTERVAL + timedelta(minutes=1))
    after_first_failure = len(fake_api.calls)
    await _advance(hass, frozen_today, RETRY_INTERVAL - timedelta(minutes=5))

    assert after_first_failure - before == 1  # fail fast: the second year isn't requested
    assert len(fake_api.calls) == after_first_failure  # nothing before RETRY_INTERVAL elapses


async def test_cache_still_serves_across_new_year_during_an_outage(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    """On 1 January the cached 'next year' list covers today, so sensors stay available."""
    frozen_today.move_to("2026-12-31 18:00:00+00:00")
    entry = await setup_entry(hass, make_entry())
    fake_api.fail(500)

    await _advance(hass, frozen_today, timedelta(hours=14))  # past local midnight

    state = get_state(hass, sensor_id(hass, entry, "Halloween"))
    assert state.state != "unavailable"
    assert state.attributes["date"] == "2027-10-31"


async def test_entities_become_unavailable_when_the_cache_no_longer_covers_today(
    hass: HomeAssistant,
    fake_api: FakeApi,
    frozen_today: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    entry = await setup_entry(hass, make_entry())
    halloween = sensor_id(hass, entry, "Halloween")
    fake_api.fail(500)

    frozen_today.move_to("2028-06-01 12:00:00+00:00")  # the cache holds 2026 and 2027 only
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert get_state(hass, halloween).state == "unavailable"
    assert entry.runtime_data.last_exception.translation_key == "update_failed"
    errors = [
        r for r in caplog.records if r.levelno == logging.ERROR and r.name == COORDINATOR_LOGGER
    ]
    assert len(errors) == 1

    fake_api.recover()
    await _advance(hass, frozen_today, RETRY_INTERVAL + timedelta(minutes=1))
    assert get_state(hass, halloween).state != "unavailable"


# -- authentication lost mid-run -----------------------------------------------


async def test_key_revoked_while_running_starts_reauth(
    hass: HomeAssistant, fake_api: FakeApi, frozen_today: FrozenDateTimeFactory
) -> None:
    entry = await setup_entry(hass, make_entry())
    halloween = sensor_id(hass, entry, "Halloween")

    fake_api.fail(401, "Invalid API key.")
    await _advance(hass, frozen_today, REFRESH_INTERVAL + timedelta(minutes=1))

    reauth_flows = [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_REAUTH
    ]
    assert len(reauth_flows) == 1
    assert get_state(hass, halloween).state == "unavailable"
