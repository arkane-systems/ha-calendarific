"""Diagnostics support for Calendarific."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .api import Holiday
from .const import CONF_API_KEY, CONF_HOLIDAYS
from .coordinator import CalendarificConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CalendarificConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for an instance, with the API key redacted."""
    coordinator = entry.runtime_data
    today = dt_util.now().date()
    tracked = entry.options.get(CONF_HOLIDAYS, {})
    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "version": f"{entry.version}.{entry.minor_version}",
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "holidays_per_year": {
                year: len(named) for year, named in sorted(coordinator.data.by_year.items())
            },
        },
        "today": today.isoformat(),
        "tracked_holidays": {
            name: _next_date(coordinator.data.next_occurrence(name, today))
            for name in tracked
        },
    }


def _next_date(holiday: Holiday | None) -> str | None:
    return None if holiday is None else holiday.day.isoformat()
