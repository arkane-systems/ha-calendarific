"""Fixtures for Calendarific tests."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.calendarific.api import API_URL

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
    """Stands in for the Calendarific HTTP API, recording every request made."""

    holidays_by_year: dict[int, list[dict[str, Any]]] = field(
        default_factory=default_holidays_by_year
    )
    status: int = 200
    detail: str = ""
    exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def fail(self, status: int, detail: str = "Something went wrong.") -> None:
        """Answer every request with an API error."""
        self.status = status
        self.detail = detail
        self.exc = None

    def raise_error(self, exc: Exception) -> None:
        """Fail every request at the network level."""
        self.exc = exc

    def recover(self) -> None:
        """Go back to answering normally."""
        self.status = 200
        self.exc = None

    async def respond(self, method: str, url: URL, data: Any) -> AiohttpClientMockResponse:
        """Answer one holidays request."""
        query = dict(url.query)
        self.calls.append({**query, "year": int(query["year"])})
        if self.exc is not None:
            return AiohttpClientMockResponse(method, url, exc=self.exc)
        if self.status != 200:
            return AiohttpClientMockResponse(
                method,
                url,
                status=self.status,
                json={
                    "meta": {
                        "code": self.status,
                        "error_type": "error",
                        "error_detail": self.detail,
                    },
                    "response": [],
                },
            )
        holidays = self.holidays_by_year.get(int(query["year"]), [])
        return AiohttpClientMockResponse(
            method,
            url,
            json={"meta": {"code": 200}, "response": {"holidays": holidays}},
        )


@pytest.fixture
def fake_api(aioclient_mock: AiohttpClientMocker) -> FakeApi:
    """Replace the HTTP layer with canned data (see common.default_holidays_by_year)."""
    fake = FakeApi()
    aioclient_mock.get(API_URL, side_effect=fake.respond)
    return fake
