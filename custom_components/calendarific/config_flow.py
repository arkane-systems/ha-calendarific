""" config flow """
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .api import fetch_holiday_names
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_STATE,
    CONF_HOLIDAYS,
    DEFAULT_ICON_NORMAL,
    DEFAULT_ICON_SOON,
    DEFAULT_ICON_TODAY,
    DEFAULT_DATE_FORMAT,
    DEFAULT_SOON,
    DEFAULT_UNIT_OF_MEASUREMENT,
    CONF_ICON_NORMAL,
    CONF_ICON_TODAY,
    CONF_ICON_SOON,
    CONF_DATE_FORMAT,
    CONF_SOON,
    CONF_UNIT_OF_MEASUREMENT,
)

_LOGGER = logging.getLogger(__name__)


def _default_holiday_config() -> dict:
    return {
        CONF_ICON_NORMAL: DEFAULT_ICON_NORMAL,
        CONF_ICON_TODAY: DEFAULT_ICON_TODAY,
        CONF_ICON_SOON: DEFAULT_ICON_SOON,
        CONF_SOON: DEFAULT_SOON,
        CONF_DATE_FORMAT: DEFAULT_DATE_FORMAT,
        CONF_UNIT_OF_MEASUREMENT: DEFAULT_UNIT_OF_MEASUREMENT,
    }


def _default_title(country: str, state: str) -> str:
    title = f"Calendarific ({country.upper()}"
    if state:
        title += f" - {state.upper()}"
    title += ")"
    return title


class CalendarificConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    "handle config flow"
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        self._instance_data = {}
        self._title = ""
        self._holiday_list = []

    async def async_step_user(self, user_input=None):
        """First step: collect the api key and country/state for this instance."""
        errors = {}
        if user_input is not None:
            country = user_input[CONF_COUNTRY]
            state = user_input.get(CONF_STATE, "")
            self._instance_data = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_COUNTRY: country,
                CONF_STATE: state,
            }
            self._title = user_input.get(CONF_NAME) or _default_title(country, state)
            self._holiday_list = await self.hass.async_add_executor_job(
                fetch_holiday_names,
                self._instance_data[CONF_API_KEY],
                country,
                state,
            )
            if not self._holiday_list:
                errors["base"] = "no_holidays_found"
            else:
                return await self.async_step_holidays()

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=""): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_COUNTRY): cv.string,
                vol.Optional(CONF_STATE, default=""): cv.string,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_holidays(self, user_input=None):
        """Second step: pick which of the available holidays to create sensors for."""
        errors = {}
        if user_input is not None:
            selected = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                holidays = {name: _default_holiday_config() for name in selected}
                return self.async_create_entry(
                    title=self._title,
                    data=self._instance_data,
                    options={CONF_HOLIDAYS: holidays},
                )

        schema = vol.Schema(
            {vol.Required(CONF_HOLIDAYS): cv.multi_select(self._holiday_list)}
        )
        return self.async_show_form(step_id="holidays", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CalendarificOptionsFlowHandler(config_entry)


class CalendarificOptionsFlowHandler(config_entries.OptionsFlow):
    """Add or remove holidays on an existing instance."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._holiday_list = []

    async def async_step_init(self, user_input=None):
        errors = {}
        current = self.config_entry.options.get(CONF_HOLIDAYS, {})

        if not self._holiday_list:
            self._holiday_list = await self.hass.async_add_executor_job(
                fetch_holiday_names,
                self.config_entry.data[CONF_API_KEY],
                self.config_entry.data[CONF_COUNTRY],
                self.config_entry.data[CONF_STATE],
            )

        if user_input is not None:
            selected = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                # Keep existing per-holiday settings for holidays that stay
                # selected; new selections get default settings.
                holidays = {
                    name: current.get(name, _default_holiday_config())
                    for name in selected
                }
                return self.async_create_entry(title="", data={CONF_HOLIDAYS: holidays})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOLIDAYS, default=list(current.keys())
                ): cv.multi_select(self._holiday_list)
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
