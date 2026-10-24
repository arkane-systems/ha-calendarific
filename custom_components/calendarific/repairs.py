"""Fix flow for the repair issues the integration raises."""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HOLIDAYS


class HolidayMissingRepairFlow(RepairsFlow):
    """Stops tracking a holiday that Calendarific no longer lists."""

    def __init__(self, entry_id: str, holiday: str) -> None:
        """Remember which instance and holiday the issue is about."""
        self._entry_id = entry_id
        self._holiday = holiday

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Start by asking for confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Remove the holiday from the instance once the user confirms."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_known_entry(self._entry_id)
            holidays = {
                name: override
                for name, override in entry.options.get(CONF_HOLIDAYS, {}).items()
                if name != self._holiday
            }
            self.hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_HOLIDAYS: holidays}
            )
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm", description_placeholders={"holiday": self._holiday}
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create the fix flow for an issue."""
    assert data is not None
    return HolidayMissingRepairFlow(str(data["entry_id"]), str(data["holiday"]))
