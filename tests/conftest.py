"""Fixtures for Calendarific tests."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.calendarific import api

from .common import FROZEN_NOW, default_holidays_by_year

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable custom integration loading for every test in this suite."""
    yield


@pytest.fixture
def frozen_today(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time at a known moment so day counts are deterministic."""
    freezer.move_to(FROZEN_NOW)
    return freezer


@dataclass
class FakeApi:
    """Stands in for the Calendarific HTTP API, recording every call made."""

    holidays_by_year: dict[int, list[dict[str, Any]]] = field(
        default_factory=default_holidays_by_year
    )
    error: dict[str, Any] | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def holidays(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Answer one holidays request."""
        self.calls.append(dict(parameters))
        if self.error is not None:
            return self.error
        return {"response": {"holidays": self.holidays_by_year.get(parameters["year"], [])}}


@pytest.fixture
def fake_api(monkeypatch: pytest.MonkeyPatch) -> FakeApi:
    """Replace the HTTP layer with canned data (see common.default_holidays_by_year)."""
    fake = FakeApi()

    def holidays(self: api.calendarificAPI, parameters: dict[str, Any]) -> dict[str, Any]:
        return fake.holidays(parameters)

    monkeypatch.setattr(api.calendarificAPI, "holidays", holidays)
    return fake
