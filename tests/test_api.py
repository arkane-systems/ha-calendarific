"""Unit tests for the Calendarific client and holiday data model (api.py)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import date
from typing import Any
from unittest.mock import patch

from aiohttp import ClientConnectionError, ClientError, ClientSession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.calendarific.api import (
    API_URL,
    REQUEST_TIMEOUT,
    CalendarificAuthError,
    CalendarificClient,
    CalendarificConnectionError,
    CalendarificRateLimitError,
    Holiday,
    HolidayData,
)

from .common import make_holiday

TODAY = date(2026, 10, 24)


def holiday(name: str, when: date, description: str = "A description.") -> Holiday:
    return Holiday(name=name, description=description, day=when)


# -- CalendarificClient ---------------------------------------------------------


@pytest.fixture
async def session(aioclient_mock: AiohttpClientMocker) -> AsyncGenerator[ClientSession]:
    client_session = aioclient_mock.create_session(asyncio.get_running_loop())
    yield client_session
    await client_session.close()


@pytest.fixture
def client(session: ClientSession) -> CalendarificClient:
    return CalendarificClient(session, "secret-key")


def ok_payload(*holidays: dict[str, Any]) -> dict[str, Any]:
    return {"meta": {"code": 200}, "response": {"holidays": list(holidays)}}


def error_payload(code: int, detail: str) -> dict[str, Any]:
    return {"meta": {"code": code, "error_type": "x", "error_detail": detail}, "response": []}


async def test_sends_key_country_year_and_location(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, json=ok_payload())

    await client.async_get_holidays("US", 2026, "US-KS")

    (_, url, _, _) = aioclient_mock.mock_calls[0]
    assert dict(url.query) == {
        "api_key": "secret-key",
        "country": "US",
        "year": "2026",
        "location": "US-KS",
    }


async def test_requests_carry_a_timeout(
    aioclient_mock: AiohttpClientMocker, session: ClientSession, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, json=ok_payload())

    with patch.object(session, "get", wraps=session.get) as get:
        await client.async_get_holidays("US", 2026)

    assert get.call_args.kwargs["timeout"].total == REQUEST_TIMEOUT


async def test_parses_holidays(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(
        API_URL,
        json=ok_payload(
            make_holiday("Christmas Day", date(2026, 12, 25), "Festival of lights."),
            make_holiday("Halloween", date(2026, 10, 31)),
        ),
    )

    assert await client.async_get_holidays("US", 2026) == [
        Holiday("Christmas Day", "Festival of lights.", date(2026, 12, 25)),
        Holiday("Halloween", "Description of Halloween.", date(2026, 10, 31)),
    ]


async def test_missing_description_becomes_empty(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    item = make_holiday("Halloween", date(2026, 10, 31))
    del item["description"]
    aioclient_mock.get(API_URL, json=ok_payload(item))

    [parsed] = await client.async_get_holidays("US", 2026)
    assert parsed.description == ""


@pytest.mark.parametrize("status", [401, 403])
async def test_auth_statuses_raise_auth_error_with_detail(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient, status: int
) -> None:
    aioclient_mock.get(API_URL, status=status, json=error_payload(status, "Bad key."))

    with pytest.raises(CalendarificAuthError, match="Bad key."):
        await client.async_get_holidays("US", 2026)


async def test_auth_error_without_a_json_body(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, status=401, text="<html>Unauthorized</html>")

    with pytest.raises(CalendarificAuthError):
        await client.async_get_holidays("US", 2026)


async def test_error_code_inside_a_200_response_is_honoured(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, json=error_payload(401, "Bad key."))

    with pytest.raises(CalendarificAuthError):
        await client.async_get_holidays("US", 2026)


async def test_rate_limit(aioclient_mock: AiohttpClientMocker, client: CalendarificClient) -> None:
    aioclient_mock.get(API_URL, status=429, json=error_payload(429, "Limit reached."))

    with pytest.raises(CalendarificRateLimitError, match="Limit reached."):
        await client.async_get_holidays("US", 2026)


@pytest.mark.parametrize("status", [500, 503])
async def test_server_errors_are_connection_errors(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient, status: int
) -> None:
    aioclient_mock.get(API_URL, status=status, json=error_payload(status, "Down."))

    with pytest.raises(CalendarificConnectionError, match="Down."):
        await client.async_get_holidays("US", 2026)


async def test_unexpected_status_without_detail(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, status=418, text="")

    with pytest.raises(CalendarificConnectionError, match="HTTP 418"):
        await client.async_get_holidays("US", 2026)


@pytest.mark.parametrize(
    "body",
    ["not json", "[]", '{"response": {}}', '{"response": {"holidays": [{"name": "x"}]}}'],
)
async def test_malformed_success_bodies_are_connection_errors(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient, body: str
) -> None:
    aioclient_mock.get(API_URL, text=body)

    with pytest.raises(CalendarificConnectionError, match="Unexpected response"):
        await client.async_get_holidays("US", 2026)


async def test_impossible_date_is_a_connection_error(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    item = make_holiday("Halloween", date(2026, 10, 31))
    item["date"]["datetime"]["month"] = 13
    aioclient_mock.get(API_URL, json=ok_payload(item))

    with pytest.raises(CalendarificConnectionError):
        await client.async_get_holidays("US", 2026)


@pytest.mark.parametrize("exc", [TimeoutError(), ClientConnectionError(), ClientError()])
async def test_network_failures_are_connection_errors(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient, exc: Exception
) -> None:
    aioclient_mock.get(API_URL, exc=exc)

    with pytest.raises(CalendarificConnectionError):
        await client.async_get_holidays("US", 2026)


async def test_error_messages_never_contain_the_api_key(
    aioclient_mock: AiohttpClientMocker, client: CalendarificClient
) -> None:
    aioclient_mock.get(API_URL, exc=ClientError(f"{API_URL}?api_key=secret-key failed"))

    with pytest.raises(CalendarificConnectionError) as excinfo:
        await client.async_get_holidays("US", 2026)

    assert "secret-key" not in str(excinfo.value)


# -- HolidayData.next_occurrence ------------------------------------------------


def data(**years: list[Holiday]) -> HolidayData:
    return HolidayData.from_lists({int(year[1:]): items for year, items in years.items()})


def test_next_occurrence_upcoming_this_year() -> None:
    result = data(y2026=[holiday("Test Day", date(2026, 11, 3))]).next_occurrence(
        "Test Day", TODAY
    )
    assert result is not None
    assert result.day == date(2026, 11, 3)


def test_next_occurrence_includes_today() -> None:
    result = data(y2026=[holiday("Test Day", TODAY)]).next_occurrence("Test Day", TODAY)
    assert result is not None
    assert result.day == TODAY


def test_next_occurrence_rolls_over_to_next_year_once_passed() -> None:
    holidays = data(
        y2026=[holiday("Test Day", date(2026, 7, 4))],
        y2027=[holiday("Test Day", date(2027, 7, 4))],
    )
    result = holidays.next_occurrence("Test Day", TODAY)
    assert result is not None
    assert result.day == date(2027, 7, 4)


def test_next_occurrence_unknown_when_passed_and_not_repeated() -> None:
    holidays = data(y2026=[holiday("Test Day", date(2026, 7, 4))], y2027=[])
    assert holidays.next_occurrence("Test Day", TODAY) is None


def test_next_occurrence_finds_a_holiday_that_only_exists_next_year() -> None:
    holidays = data(y2026=[], y2027=[holiday("Inauguration Day", date(2027, 1, 20))])
    result = holidays.next_occurrence("Inauguration Day", TODAY)
    assert result is not None
    assert result.day == date(2027, 1, 20)


def test_next_occurrence_unknown_name() -> None:
    assert data(y2026=[]).next_occurrence("Nonexistent", TODAY) is None


def test_next_occurrence_uses_the_supplied_today_not_the_system_clock() -> None:
    # Regression: sensors once rolled over at system-clock midnight (often UTC)
    # rather than Home Assistant's configured local midnight.
    holidays = data(
        y2026=[holiday("Test Day", date(2026, 6, 15))],
        y2027=[holiday("Test Day", date(2027, 6, 15))],
    )
    before = holidays.next_occurrence("Test Day", date(2026, 6, 15))
    after = holidays.next_occurrence("Test Day", date(2026, 6, 16))
    assert before is not None and before.day == date(2026, 6, 15)
    assert after is not None and after.day == date(2027, 6, 15)


def test_first_of_duplicate_names_wins() -> None:
    holidays = data(
        y2026=[
            holiday("Test Day", date(2026, 11, 1), "first"),
            holiday("Test Day", date(2026, 11, 2), "second"),
        ]
    )
    result = holidays.next_occurrence("Test Day", TODAY)
    assert result is not None
    assert result.description == "first"


def test_covers() -> None:
    holidays = data(y2026=[], y2027=[])
    assert holidays.covers(date(2026, 1, 1))
    assert holidays.covers(date(2027, 12, 31))
    assert not holidays.covers(date(2028, 1, 1))


# -- HolidayData.next_holiday ---------------------------------------------------


def test_next_holiday_returns_the_soonest() -> None:
    holidays = data(
        y2026=[
            holiday("Later Day", date(2026, 11, 20)),
            holiday("Soon Day", date(2026, 10, 29)),
        ]
    )
    result = holidays.next_holiday(["Later Day", "Soon Day"], TODAY)
    assert result is not None
    assert result.name == "Soon Day"


def test_next_holiday_breaks_date_ties_on_name() -> None:
    same_day = date(2026, 10, 29)
    holidays = data(y2026=[holiday("Zebra Day", same_day), holiday("Apple Day", same_day)])
    result = holidays.next_holiday(["Zebra Day", "Apple Day"], TODAY)
    assert result is not None
    assert result.name == "Apple Day"


def test_next_holiday_skips_unknown_names() -> None:
    holidays = data(y2026=[holiday("Soon Day", date(2026, 10, 29))])
    result = holidays.next_holiday(["Nonexistent", "Soon Day"], TODAY)
    assert result is not None
    assert result.name == "Soon Day"


def test_next_holiday_none_without_candidates() -> None:
    holidays = data(y2026=[])
    assert holidays.next_holiday(["Nonexistent"], TODAY) is None
    assert holidays.next_holiday([], TODAY) is None


# -- HolidayData.occurrences ----------------------------------------------------


def test_occurrences_filters_by_range_and_name_and_sorts() -> None:
    holidays = data(
        y2026=[
            holiday("Christmas Day", date(2026, 12, 25)),
            holiday("Halloween", date(2026, 10, 31)),
            holiday("Independence Day", date(2026, 7, 4)),
        ]
    )
    found = holidays.occurrences(
        ["Christmas Day", "Halloween"], date(2026, 7, 1), date(2026, 12, 31)
    )
    assert [h.name for h in found] == ["Halloween", "Christmas Day"]


def test_occurrences_spans_years_and_includes_both_ends() -> None:
    holidays = data(
        y2026=[holiday("New Year", date(2026, 12, 31))],
        y2027=[holiday("New Year", date(2027, 1, 1))],
    )
    found = holidays.occurrences(["New Year"], date(2026, 12, 31), date(2027, 1, 1))
    assert [h.day for h in found] == [date(2026, 12, 31), date(2027, 1, 1)]


def test_occurrences_ignores_years_without_data() -> None:
    holidays = data(y2026=[holiday("Halloween", date(2026, 10, 31))])
    assert holidays.occurrences(["Halloween"], date(2030, 1, 1), date(2030, 12, 31)) == []
