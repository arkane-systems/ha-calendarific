""" config flow """
from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    CalendarificAuthError,
    CalendarificClient,
    CalendarificError,
    CalendarificRateLimitError,
)
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_STATE,
    CONF_HOLIDAYS,
    CONF_DEFAULTS,
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

CONF_RESET_TO_DEFAULT = "reset_to_default"


async def _async_fetch_holiday_names(
    hass: HomeAssistant, api_key: str, country: str, state: str
) -> list[str]:
    """Return the distinct holiday names available for a country/state this year."""
    client = CalendarificClient(async_get_clientsession(hass), api_key)
    holidays = await client.async_get_holidays(country, dt_util.now().year, state)
    return list(dict.fromkeys(holiday.name for holiday in holidays))


def _error_key(err: CalendarificError) -> str:
    """Map an API error to the translation key shown to the user."""
    if isinstance(err, CalendarificAuthError):
        return "invalid_auth"
    if isinstance(err, CalendarificRateLimitError):
        return "rate_limited"
    return "cannot_connect"


def _hardcoded_defaults() -> dict:
    """The integration's built-in fallback settings, used to seed the instance defaults form."""
    return {
        CONF_ICON_NORMAL: DEFAULT_ICON_NORMAL,
        CONF_ICON_TODAY: DEFAULT_ICON_TODAY,
        CONF_ICON_SOON: DEFAULT_ICON_SOON,
        CONF_SOON: DEFAULT_SOON,
        CONF_DATE_FORMAT: DEFAULT_DATE_FORMAT,
        CONF_UNIT_OF_MEASUREMENT: DEFAULT_UNIT_OF_MEASUREMENT,
    }


def _holiday_settings_schema(
    values: dict, include_reset: bool = False, include_name: bool = False
) -> vol.Schema:
    """Build the icon/date-format/etc. form, pre-filled from values (falling back to hardcoded defaults).

    include_name is only for the per-holiday customize form - a custom name
    doesn't make sense as an instance-wide default shared by every holiday.
    """
    hardcoded = _hardcoded_defaults()
    schema = {}
    if include_name:
        schema[vol.Optional(CONF_NAME, default=values.get(CONF_NAME, ""))] = cv.string
    schema.update({
        vol.Required(
            CONF_ICON_NORMAL, default=values.get(CONF_ICON_NORMAL, hardcoded[CONF_ICON_NORMAL])
        ): cv.string,
        vol.Required(
            CONF_ICON_TODAY, default=values.get(CONF_ICON_TODAY, hardcoded[CONF_ICON_TODAY])
        ): cv.string,
        vol.Required(
            CONF_ICON_SOON, default=values.get(CONF_ICON_SOON, hardcoded[CONF_ICON_SOON])
        ): cv.string,
        vol.Required(CONF_SOON, default=values.get(CONF_SOON, hardcoded[CONF_SOON])): int,
        vol.Required(
            CONF_DATE_FORMAT, default=values.get(CONF_DATE_FORMAT, hardcoded[CONF_DATE_FORMAT])
        ): cv.string,
        vol.Required(
            CONF_UNIT_OF_MEASUREMENT,
            default=values.get(CONF_UNIT_OF_MEASUREMENT, hardcoded[CONF_UNIT_OF_MEASUREMENT]),
        ): cv.string,
    })
    if include_reset:
        schema[vol.Optional(CONF_RESET_TO_DEFAULT, default=False)] = cv.boolean
    return vol.Schema(schema)


def _default_title(country: str, state: str) -> str:
    title = f"Calendarific ({country.upper()}"
    if state:
        title += f" - {state.upper()}"
    title += ")"
    return title


class CalendarificConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    "handle config flow"
    VERSION = 1

    def __init__(self) -> None:
        self._instance_data = {}
        self._instance_defaults = {}
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
            try:
                self._holiday_list = await _async_fetch_holiday_names(
                    self.hass, self._instance_data[CONF_API_KEY], country, state
                )
            except CalendarificError as err:
                errors["base"] = _error_key(err)
            else:
                if not self._holiday_list:
                    errors["base"] = "no_holidays_found"
                else:
                    return await self.async_step_defaults()

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=""): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_COUNTRY): cv.string,
                vol.Optional(CONF_STATE, default=""): cv.string,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_defaults(self, user_input=None):
        """Second step: instance-wide defaults, applied to every holiday unless overridden."""
        if user_input is not None:
            self._instance_defaults = user_input
            return await self.async_step_holidays()

        schema = _holiday_settings_schema(_hardcoded_defaults())
        return self.async_show_form(step_id="defaults", data_schema=schema)

    async def async_step_holidays(self, user_input=None):
        """Third step: pick which of the available holidays to create sensors for."""
        errors = {}
        if user_input is not None:
            selected = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                # No per-holiday overrides at creation time - just the instance defaults.
                holidays = {name: {} for name in selected}
                return self.async_create_entry(
                    title=self._title,
                    data=self._instance_data,
                    options={CONF_DEFAULTS: self._instance_defaults, CONF_HOLIDAYS: holidays},
                )

        schema = vol.Schema(
            {vol.Required(CONF_HOLIDAYS): cv.multi_select(self._holiday_list)}
        )
        return self.async_show_form(step_id="holidays", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """The API key was rejected: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Collect and verify a replacement API key."""
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _async_fetch_holiday_names(
                    self.hass,
                    user_input[CONF_API_KEY],
                    entry.data[CONF_COUNTRY],
                    entry.data[CONF_STATE],
                )
            except CalendarificError as err:
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): cv.string}),
            errors=errors,
            description_placeholders={"title": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return CalendarificOptionsFlowHandler()


class CalendarificOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Manage an existing instance: its holidays, its defaults, and per-holiday overrides.

    Reloads the entry automatically when the options change. Deliberately
    doesn't set self.config_entry in __init__ - recent HA versions populate it
    automatically before async_step_init runs, and assigning it here raises
    rather than just warning.
    """

    def __init__(self) -> None:
        self._holiday_list = []
        self._selected_holiday = None

    async def _fetch_holiday_list(self):
        if not self._holiday_list:
            self._holiday_list = await _async_fetch_holiday_names(
                self.hass,
                self.config_entry.data[CONF_API_KEY],
                self.config_entry.data[CONF_COUNTRY],
                self.config_entry.data[CONF_STATE],
            )
        return self._holiday_list

    async def async_step_init(self, user_input=None):
        """Menu: manage which holidays are tracked, edit instance defaults, or customize one holiday."""
        if user_input is not None:
            action = user_input["action"]
            if action == "holidays":
                return await self.async_step_holidays()
            if action == "defaults":
                return await self.async_step_defaults()
            return await self.async_step_customize()

        schema = vol.Schema(
            {
                vol.Required("action", default="holidays"): vol.In(
                    {
                        "holidays": "Add or remove holidays",
                        "defaults": "Edit instance defaults",
                        "customize": "Customize a specific holiday",
                    }
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_holidays(self, user_input=None):
        """Add or remove holidays. Removing one discards any override it had."""
        errors = {}
        current_holidays = self.config_entry.options.get(CONF_HOLIDAYS, {})
        try:
            holiday_list = await self._fetch_holiday_list()
        except CalendarificError as err:
            return self.async_abort(reason=_error_key(err))

        if user_input is not None:
            selected = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                holidays = {name: current_holidays.get(name, {}) for name in selected}
                return self.async_create_entry(
                    title="",
                    data={**self.config_entry.options, CONF_HOLIDAYS: holidays},
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOLIDAYS, default=list(current_holidays.keys())
                ): cv.multi_select(holiday_list)
            }
        )
        return self.async_show_form(step_id="holidays", data_schema=schema, errors=errors)

    async def async_step_defaults(self, user_input=None):
        """Edit the instance-wide defaults every holiday inherits unless it has its own override."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_DEFAULTS: user_input},
            )

        current_defaults = self.config_entry.options.get(CONF_DEFAULTS, _hardcoded_defaults())
        schema = _holiday_settings_schema(current_defaults)
        return self.async_show_form(step_id="defaults", data_schema=schema)

    async def async_step_customize(self, user_input=None):
        """Pick which tracked holiday to override the instance defaults for."""
        current_holidays = self.config_entry.options.get(CONF_HOLIDAYS, {})
        if not current_holidays:
            return self.async_abort(reason="no_holidays_configured")

        if user_input is not None:
            self._selected_holiday = user_input["holiday"]
            return await self.async_step_customize_values()

        schema = vol.Schema({vol.Required("holiday"): vol.In(sorted(current_holidays.keys()))})
        return self.async_show_form(step_id="customize", data_schema=schema)

    async def async_step_customize_values(self, user_input=None):
        """Set (or clear) this holiday's overrides on top of the instance defaults."""
        defaults = self.config_entry.options.get(CONF_DEFAULTS, _hardcoded_defaults())
        current_holidays = self.config_entry.options.get(CONF_HOLIDAYS, {})
        override = current_holidays.get(self._selected_holiday, {})

        if user_input is not None:
            name = user_input.pop(CONF_NAME, "").strip()
            if user_input.pop(CONF_RESET_TO_DEFAULT, False):
                new_override = {}
            else:
                # Only keep values that actually differ from the instance defaults -
                # matching the default is equivalent to not overriding it. A custom
                # name has no instance default to compare against - blank means "use
                # the holiday's own name" rather than an override.
                new_override = {k: v for k, v in user_input.items() if v != defaults.get(k)}
                if name:
                    new_override[CONF_NAME] = name
            holidays = {**current_holidays, self._selected_holiday: new_override}
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_HOLIDAYS: holidays},
            )

        effective = {**defaults, **override}
        schema = _holiday_settings_schema(effective, include_reset=True, include_name=True)
        return self.async_show_form(
            step_id="customize_values",
            data_schema=schema,
            description_placeholders={"holiday": self._selected_holiday},
        )
