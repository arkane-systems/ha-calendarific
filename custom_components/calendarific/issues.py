"""Repair issues raised by the integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from .api import HolidayData
from .const import CONF_HOLIDAYS, DOMAIN

ISSUE_HOLIDAY_MISSING = "holiday_missing"


def _issue_prefix(entry_id: str) -> str:
    return f"{ISSUE_HOLIDAY_MISSING}_{entry_id}_"


def holiday_missing_issue_id(entry_id: str, holiday_name: str) -> str:
    """Return the repair issue ID for a tracked holiday Calendarific no longer lists."""
    return _issue_prefix(entry_id) + slugify(holiday_name)


@callback
def async_sync_missing_holiday_issues(
    hass: HomeAssistant, entry: ConfigEntry, data: HolidayData
) -> None:
    """Raise an issue for each tracked holiday absent from the data; clear the rest."""
    wanted = {
        holiday_missing_issue_id(entry.entry_id, name): name
        for name in entry.options.get(CONF_HOLIDAYS, {})
        if not data.knows(name)
    }
    for issue_id in _existing_issue_ids(hass, entry.entry_id) - wanted.keys():
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    for issue_id, name in wanted.items():
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_HOLIDAY_MISSING,
            translation_placeholders={"holiday": name, "title": entry.title},
            data={"entry_id": entry.entry_id, "holiday": name},
        )


@callback
def async_delete_issues(hass: HomeAssistant, entry_id: str) -> None:
    """Remove every issue this instance raised."""
    for issue_id in _existing_issue_ids(hass, entry_id):
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def _existing_issue_ids(hass: HomeAssistant, entry_id: str) -> set[str]:
    prefix = _issue_prefix(entry_id)
    return {
        issue_id
        for domain, issue_id in ir.async_get(hass).issues
        if domain == DOMAIN and issue_id.startswith(prefix)
    }
