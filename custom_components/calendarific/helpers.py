"""Small helpers shared by the config flow and entry migration."""

from __future__ import annotations

from homeassistant.util import slugify


def default_title(country: str, state: str) -> str:
    """Return the title generated for an instance that wasn't given a name."""
    title = f"Calendarific ({country.upper()}"
    if state:
        title += f" - {state.upper()}"
    title += ")"
    return title


def instance_unique_id(country: str, state: str) -> str:
    """Identify an instance by its country/state, so each can be added only once."""
    unique_id = country.strip().lower()
    if state.strip():
        unique_id += f"-{state.strip().lower()}"
    return unique_id


def holiday_unique_id(entry_id: str, holiday_name: str) -> str:
    """Return the unique ID of a holiday's sensor, scoped to its instance."""
    return f"{entry_id}_{slugify(holiday_name)}"


def next_holiday_unique_id(entry_id: str) -> str:
    """Return the unique ID of an instance's Next Holiday sensor."""
    return f"{entry_id}_next_holiday"


def calendar_unique_id(entry_id: str) -> str:
    """Return the unique ID of an instance's calendar."""
    return f"{entry_id}_calendar"
