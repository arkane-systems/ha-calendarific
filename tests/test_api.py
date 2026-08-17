"""Unit tests for the Calendarific API client and holiday cache (api.py).

These exercise pure logic only, via monkeypatched requests.get/calendarificAPI.holidays -
no network access and no homeassistant dependency required.
"""
import json
from datetime import date, timedelta

import api


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.text = json.dumps(payload)


def holiday(name, year, month, day, description="A description."):
    return {
        "name": name,
        "description": description,
        "date": {"datetime": {"year": year, "month": month, "day": day}},
    }


# -- calendarificAPI.holidays -------------------------------------------------


def test_holidays_injects_api_key_when_missing(monkeypatch):
    captured = {}

    def fake_get(url, params):
        captured.update(params)
        return FakeResponse(200, {"response": {"holidays": []}})

    monkeypatch.setattr(api.requests, "get", fake_get)
    api.calendarificAPI("secret-key").holidays({"country": "US"})
    assert captured["api_key"] == "secret-key"


def test_holidays_preserves_explicit_api_key(monkeypatch):
    captured = {}

    def fake_get(url, params):
        captured.update(params)
        return FakeResponse(200, {"response": {"holidays": []}})

    monkeypatch.setattr(api.requests, "get", fake_get)
    api.calendarificAPI("default-key").holidays({"country": "US", "api_key": "explicit-key"})
    assert captured["api_key"] == "explicit-key"


def test_holidays_synthesizes_error_on_non_200_without_error_field(monkeypatch):
    monkeypatch.setattr(
        api.requests, "get", lambda url, params: FakeResponse(500, {"meta": {"code": 500}})
    )
    result = api.calendarificAPI("key").holidays({"country": "US"})
    assert result["error"] == "Unknown error."


def test_holidays_preserves_existing_error_field(monkeypatch):
    monkeypatch.setattr(
        api.requests,
        "get",
        lambda url, params: FakeResponse(401, {"error": "Invalid API key.", "meta": {"code": 401}}),
    )
    result = api.calendarificAPI("bad-key").holidays({"country": "US"})
    assert result["error"] == "Invalid API key."


# -- fetch_holiday_names -------------------------------------------------------


def test_fetch_holiday_names_returns_names(monkeypatch):
    def fake_holidays(self, parameters):
        return {"response": {"holidays": [{"name": "New Year's Day"}, {"name": "Christmas Day"}]}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    assert api.fetch_holiday_names("key", "US", "") == ["New Year's Day", "Christmas Day"]


def test_fetch_holiday_names_returns_empty_on_error(monkeypatch):
    monkeypatch.setattr(
        api.calendarificAPI, "holidays", lambda self, parameters: {"error": "Invalid API key."}
    )
    assert api.fetch_holiday_names("bad-key", "US", "") == []


# -- CalendarificApiReader.get_date -------------------------------------------


def test_get_date_returns_current_year_date_when_upcoming(monkeypatch):
    today = date.today()
    future = today + timedelta(days=10)

    def fake_holidays(self, parameters):
        if parameters["year"] == today.year:
            return {"response": {"holidays": [holiday("Test Day", future.year, future.month, future.day)]}}
        return {"response": {"holidays": []}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_date("Test Day") == future


def test_get_date_returns_today_when_holiday_is_today(monkeypatch):
    today = date.today()

    def fake_holidays(self, parameters):
        if parameters["year"] == today.year:
            return {"response": {"holidays": [holiday("Test Day", today.year, today.month, today.day)]}}
        return {"response": {"holidays": []}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_date("Test Day") == today


def test_get_date_rolls_over_to_next_year_when_passed(monkeypatch):
    today = date.today()
    past = today - timedelta(days=5)
    next_occurrence = date(today.year + 1, past.month, past.day)

    def fake_holidays(self, parameters):
        if parameters["year"] == today.year:
            return {"response": {"holidays": [holiday("Test Day", past.year, past.month, past.day)]}}
        return {
            "response": {
                "holidays": [
                    holiday("Test Day", next_occurrence.year, next_occurrence.month, next_occurrence.day)
                ]
            }
        }

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_date("Test Day") == next_occurrence


def test_get_date_returns_placeholder_when_not_found(monkeypatch):
    monkeypatch.setattr(
        api.calendarificAPI, "holidays", lambda self, parameters: {"response": {"holidays": []}}
    )
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_date("Nonexistent") == "-"


def test_get_date_returns_placeholder_when_passed_and_missing_next_year(monkeypatch):
    today = date.today()
    past = today - timedelta(days=5)

    def fake_holidays(self, parameters):
        if parameters["year"] == today.year:
            return {"response": {"holidays": [holiday("Test Day", past.year, past.month, past.day)]}}
        return {"response": {"holidays": []}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_date("Test Day") == "-"


# -- CalendarificApiReader.get_description / get_holidays ---------------------


def test_get_description_found(monkeypatch):
    def fake_holidays(self, parameters):
        if parameters["year"] == date.today().year:
            return {"response": {"holidays": [holiday("Test Day", 2000, 1, 1, description="Some description.")]}}
        return {"response": {"holidays": []}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_description("Test Day") == "Some description."


def test_get_description_not_found(monkeypatch):
    monkeypatch.setattr(
        api.calendarificAPI, "holidays", lambda self, parameters: {"response": {"holidays": []}}
    )
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_description("Nonexistent") == "NOT FOUND"


def test_get_holidays_lists_current_year_names_only(monkeypatch):
    def fake_holidays(self, parameters):
        if parameters["year"] == date.today().year:
            return {"response": {"holidays": [holiday("A", 2000, 1, 1), holiday("B", 2000, 1, 2)]}}
        return {"response": {"holidays": [holiday("C", 2001, 1, 1)]}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")
    assert reader.get_holidays() == ["A", "B"]


# -- CalendarificApiReader.update ---------------------------------------------


def test_update_only_fetches_once_per_day(monkeypatch):
    calls = []

    def fake_holidays(self, parameters):
        calls.append(parameters["year"])
        return {"response": {"holidays": []}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("key", "US", "")  # __init__ triggers the first update()
    assert len(calls) == 2  # current year + next year

    reader.update()  # same day - should be a no-op
    assert len(calls) == 2


def test_update_stops_and_logs_once_on_current_year_error(monkeypatch):
    calls = []

    def fake_holidays(self, parameters):
        calls.append(parameters["year"])
        return {"error": "Invalid API key.", "meta": {"error_detail": "Invalid API key."}}

    monkeypatch.setattr(api.calendarificAPI, "holidays", fake_holidays)
    reader = api.CalendarificApiReader("bad-key", "US", "")

    assert calls == [date.today().year]  # next year never requested
    assert reader._error_logged is True
    assert reader.get_holidays() == []
