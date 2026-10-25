"""Calendarific API client and holiday data model.

This module deliberately has no homeassistant dependency: the HTTP session is
injected by the caller, and "today" is always passed in rather than read from
the system clock (which is not necessarily Home Assistant's configured time
zone).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from http import HTTPStatus
import json
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

API_URL = "https://calendarific.com/api/v2/holidays"
REQUEST_TIMEOUT = 15


class CalendarificError(Exception):
    """Base class for errors talking to Calendarific."""


class CalendarificConnectionError(CalendarificError):
    """The API could not be reached or returned something unusable (transient)."""


class CalendarificRateLimitError(CalendarificError):
    """The account's monthly request limit has been reached."""


class CalendarificAuthError(CalendarificError):
    """The API key is missing, invalid or its subscription has expired."""


@dataclass(frozen=True, slots=True)
class Holiday:
    """One occurrence of a holiday."""

    name: str
    description: str
    day: date


@dataclass(frozen=True, slots=True)
class HolidayData:
    """Holidays for one or more consecutive calendar years."""

    by_year: Mapping[int, Mapping[str, Holiday]]

    @classmethod
    def from_lists(cls, lists: Mapping[int, Iterable[Holiday]]) -> HolidayData:
        """Index each year's holidays by name (the first of any duplicates wins)."""
        by_year: dict[int, dict[str, Holiday]] = {}
        for year, holidays in lists.items():
            named: dict[str, Holiday] = {}
            for holiday in holidays:
                named.setdefault(holiday.name, holiday)
            by_year[year] = named
        return cls(by_year)

    def covers(self, today: date) -> bool:
        """Whether this data includes the whole of today's year."""
        return today.year in self.by_year

    def knows(self, name: str) -> bool:
        """Whether any fetched year lists a holiday by this name."""
        return any(name in named for named in self.by_year.values())

    def next_occurrence(self, name: str, today: date) -> Holiday | None:
        """Return the first occurrence of a holiday on or after today, if known."""
        for year in sorted(self.by_year):
            if year < today.year:
                continue
            holiday = self.by_year[year].get(name)
            if holiday is not None and holiday.day >= today:
                return holiday
        return None

    def next_holiday(self, names: Iterable[str], today: date) -> Holiday | None:
        """Return the soonest upcoming holiday among names; ties break on name."""
        candidates = [
            holiday
            for name in names
            if (holiday := self.next_occurrence(name, today)) is not None
        ]
        return min(candidates, key=lambda holiday: (holiday.day, holiday.name), default=None)

    def occurrences(self, names: Iterable[str], start: date, end: date) -> list[Holiday]:
        """Return every occurrence of the named holidays between start and end inclusive."""
        wanted = list(names)
        found = [
            holiday
            for year in range(start.year, end.year + 1)
            for name in wanted
            if (holiday := self.by_year.get(year, {}).get(name)) is not None
            and start <= holiday.day <= end
        ]
        return sorted(found, key=lambda holiday: (holiday.day, holiday.name))


class CalendarificClient:
    """Thin async wrapper around the Calendarific v2 holidays endpoint."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        """Initialize the client with an aiohttp session owned by the caller."""
        self._session = session
        self._api_key = api_key

    async def async_get_holidays(
        self, country: str, year: int, state: str = ""
    ) -> list[Holiday]:
        """Fetch the holidays for a country (and optionally state) in a given year."""
        params: dict[str, str | int] = {
            "api_key": self._api_key,
            "country": country,
            "year": year,
            "location": state,
        }
        # Exception messages below never include str(err): aiohttp errors can
        # embed the request URL, which carries the API key.
        try:
            async with self._session.get(
                API_URL, params=params, timeout=ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                status = response.status
                body = await response.text()
        except TimeoutError as err:
            raise CalendarificConnectionError("Timed out talking to Calendarific") from err
        except ClientError as err:
            raise CalendarificConnectionError("Error talking to Calendarific") from err

        payload = _parse_json(body)
        code = _meta_code(payload) if status == HTTPStatus.OK else status
        if code == HTTPStatus.OK:
            return _parse_holidays(payload)

        detail = _error_detail(payload)
        if code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise CalendarificAuthError(detail or "Invalid or expired API key")
        if code == HTTPStatus.TOO_MANY_REQUESTS:
            raise CalendarificRateLimitError(detail or "Monthly request limit reached")
        raise CalendarificConnectionError(detail or f"Calendarific returned HTTP {code}")


def _parse_json(body: str) -> Any:
    """Decode a response body, returning None if it is not valid JSON."""
    try:
        return json.loads(body)
    except ValueError:
        return None


def _meta(payload: Any) -> Mapping[str, Any]:
    meta = payload.get("meta") if isinstance(payload, dict) else None
    return meta if isinstance(meta, dict) else {}


def _meta_code(payload: Any) -> int:
    """Return the status the API reports inside a 200 response (200 if absent)."""
    code = _meta(payload).get("code", HTTPStatus.OK)
    return code if isinstance(code, int) else HTTPStatus.OK


def _error_detail(payload: Any) -> str:
    detail = _meta(payload).get("error_detail")
    return str(detail) if detail else ""


def _parse_holidays(payload: Any) -> list[Holiday]:
    try:
        return [
            Holiday(
                name=item["name"],
                description=item.get("description") or "",
                day=date(
                    item["date"]["datetime"]["year"],
                    item["date"]["datetime"]["month"],
                    item["date"]["datetime"]["day"],
                ),
            )
            for item in payload["response"]["holidays"]
        ]
    except (KeyError, TypeError, ValueError, AttributeError) as err:
        raise CalendarificConnectionError("Unexpected response from Calendarific") from err
