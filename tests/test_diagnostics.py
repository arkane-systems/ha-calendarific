"""Tests for the diagnostics download."""

from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.calendarific.diagnostics import async_get_config_entry_diagnostics

from .common import make_entry, setup_entry
from .conftest import FakeApi

pytestmark = pytest.mark.usefixtures("frozen_today")


async def test_diagnostics_redact_the_api_key(hass: HomeAssistant, fake_api: FakeApi) -> None:
    entry = await setup_entry(
        hass,
        make_entry(
            title="Home", country="US", state="KS", api_key="very-secret",
            holidays={"Halloween": {"name": "Spooky"}, "Boxing Day": {}},
        ),
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "very-secret" not in json.dumps(diagnostics)
    assert diagnostics["entry"]["data"] == {
        "api_key": "**REDACTED**",
        "country": "US",
        "state": "KS",
    }
    assert diagnostics["entry"]["title"] == "Home"
    assert diagnostics["entry"]["unique_id"] == "us-ks"
    assert diagnostics["entry"]["version"] == "1.3"
    assert diagnostics["entry"]["options"]["holidays"]["Halloween"] == {"name": "Spooky"}
    assert diagnostics["today"] == "2026-10-24"


async def test_diagnostics_describe_the_cache_and_each_holiday(
    hass: HomeAssistant, fake_api: FakeApi
) -> None:
    entry = await setup_entry(hass, make_entry(holidays={"Halloween": {}, "Boxing Day": {}}))

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["coordinator"] == {
        "last_update_success": True,
        "update_interval": "1 day, 0:00:00",
        "holidays_per_year": {2026: 4, 2027: 4},
    }
    assert diagnostics["tracked_holidays"] == {"Halloween": "2026-10-31", "Boxing Day": None}


async def test_diagnostics_are_served_through_home_assistant(
    hass: HomeAssistant, fake_api: FakeApi, hass_client: ClientSessionGenerator
) -> None:
    entry = await setup_entry(hass, make_entry(api_key="very-secret"))
    assert await async_setup_component(hass, "diagnostics", {})
    client = await hass_client()

    response = await client.get(f"/api/diagnostics/config_entry/{entry.entry_id}")

    assert response.status == 200
    body = await response.json()
    assert body["data"]["entry"]["data"]["api_key"] == "**REDACTED**"
    assert "very-secret" not in json.dumps(body)
