"""Small helpers shared by the config flow and entry migration."""

from __future__ import annotations


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
