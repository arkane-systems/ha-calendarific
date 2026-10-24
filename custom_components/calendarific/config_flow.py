"""Config flow, reauth, reconfigure and options flow for Calendarific."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .api import (
    CalendarificAuthError,
    CalendarificClient,
    CalendarificError,
    CalendarificRateLimitError,
)
from .const import (
    CONF_API_KEY,
    CONF_COUNTRY,
    CONF_DATE_FORMAT,
    CONF_DEFAULTS,
    CONF_HOLIDAYS,
    CONF_ICON_NORMAL,
    CONF_ICON_SOON,
    CONF_ICON_TODAY,
    CONF_SOON,
    CONF_STATE,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_DATE_FORMAT,
    DEFAULT_ICON_NORMAL,
    DEFAULT_ICON_SOON,
    DEFAULT_ICON_TODAY,
    DEFAULT_SOON,
    DOMAIN,
)
from .coordinator import CalendarificConfigEntry
from .helpers import default_title, instance_unique_id

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


def _hardcoded_defaults() -> dict[str, Any]:
    """The integration's built-in fallback settings, used to seed the instance defaults form."""
    return {
        CONF_ICON_NORMAL: DEFAULT_ICON_NORMAL,
        CONF_ICON_TODAY: DEFAULT_ICON_TODAY,
        CONF_ICON_SOON: DEFAULT_ICON_SOON,
        CONF_SOON: DEFAULT_SOON,
        CONF_DATE_FORMAT: DEFAULT_DATE_FORMAT,
    }


def _holiday_settings_schema(
    values: Mapping[str, Any], include_reset: bool = False, include_name: bool = False
) -> vol.Schema:
    """Build the icon/date-format/etc. form, pre-filled from values (falling back to hardcoded defaults).

    include_name is only for the per-holiday customize form - a custom name
    doesn't make sense as an instance-wide default shared by every holiday.
    """
    hardcoded = _hardcoded_defaults()
    schema: dict[vol.Marker, Any] = {}
    if include_name:
        schema[vol.Optional(CONF_NAME, default=values.get(CONF_NAME, ""))] = cv.string
    schema.update(
        {
            vol.Required(
                CONF_ICON_NORMAL,
                default=values.get(CONF_ICON_NORMAL, hardcoded[CONF_ICON_NORMAL]),
            ): cv.string,
            vol.Required(
                CONF_ICON_TODAY,
                default=values.get(CONF_ICON_TODAY, hardcoded[CONF_ICON_TODAY]),
            ): cv.string,
            vol.Required(
                CONF_ICON_SOON,
                default=values.get(CONF_ICON_SOON, hardcoded[CONF_ICON_SOON]),
            ): cv.string,
            vol.Required(CONF_SOON, default=values.get(CONF_SOON, hardcoded[CONF_SOON])): int,
            vol.Required(
                CONF_DATE_FORMAT,
                default=values.get(CONF_DATE_FORMAT, hardcoded[CONF_DATE_FORMAT]),
            ): cv.string,
        }
    )
    if include_reset:
        schema[vol.Optional(CONF_RESET_TO_DEFAULT, default=False)] = cv.boolean
    return vol.Schema(schema)


class CalendarificConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up, reauthenticate and reconfigure a Calendarific instance."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    def __init__(self) -> None:
        """Initialize the flow."""
        self._instance_data: dict[str, str] = {}
        self._instance_defaults: dict[str, Any] = {}
        self._title = ""
        self._holiday_list: list[str] = []
        self._new_instance_data: dict[str, str] = {}

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First step: collect the api key and country/state for this instance."""
        errors: dict[str, str] = {}
        if user_input is not None:
            country = user_input[CONF_COUNTRY].strip()
            state = user_input.get(CONF_STATE, "").strip()
            await self.async_set_unique_id(instance_unique_id(country, state))
            self._abort_if_unique_id_configured()
            self._instance_data = {
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_COUNTRY: country,
                CONF_STATE: state,
            }
            self._title = user_input.get(CONF_NAME) or default_title(country, state)
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

    async def async_step_defaults(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Second step: instance-wide defaults, applied to every holiday unless overridden."""
        if user_input is not None:
            self._instance_defaults = dict(user_input)
            return await self.async_step_holidays()

        schema = _holiday_settings_schema(_hardcoded_defaults())
        return self.async_show_form(step_id="defaults", data_schema=schema)

    async def async_step_holidays(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Third step: pick which of the available holidays to create sensors for."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected: list[str] = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                # No per-holiday overrides at creation time - just the instance defaults.
                holidays: dict[str, dict[str, Any]] = {name: {} for name in selected}
                return self.async_create_entry(
                    title=self._title,
                    data=self._instance_data,
                    options={CONF_DEFAULTS: self._instance_defaults, CONF_HOLIDAYS: holidays},
                )

        schema = vol.Schema({vol.Required(CONF_HOLIDAYS): cv.multi_select(self._holiday_list)})
        return self.async_show_form(step_id="holidays", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The API key was rejected: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect and verify a replacement API key."""
        errors: dict[str, str] = {}
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

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the API key, country or state of an existing instance."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            country = user_input[CONF_COUNTRY].strip()
            state = user_input.get(CONF_STATE, "").strip()
            api_key = user_input[CONF_API_KEY]
            unique_id = instance_unique_id(country, state)
            if any(
                other.unique_id == unique_id
                for other in self._async_current_entries(include_ignore=False)
                if other.entry_id != entry.entry_id
            ):
                errors["base"] = "already_configured"
            else:
                try:
                    self._holiday_list = await _async_fetch_holiday_names(
                        self.hass, api_key, country, state
                    )
                except CalendarificError as err:
                    errors["base"] = _error_key(err)
                else:
                    if not self._holiday_list:
                        errors["base"] = "no_holidays_found"
                    elif unique_id == instance_unique_id(
                        entry.data[CONF_COUNTRY], entry.data[CONF_STATE]
                    ):
                        # Same place (perhaps a new key): nothing else to re-pick.
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates={
                                CONF_API_KEY: api_key,
                                CONF_COUNTRY: country,
                                CONF_STATE: state,
                            },
                        )
                    else:
                        self._new_instance_data = {
                            CONF_API_KEY: api_key,
                            CONF_COUNTRY: country,
                            CONF_STATE: state,
                        }
                        return await self.async_step_reconfigure_holidays()

        schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY, default=entry.data[CONF_API_KEY]): cv.string,
                vol.Required(CONF_COUNTRY, default=entry.data[CONF_COUNTRY]): cv.string,
                vol.Optional(CONF_STATE, default=entry.data[CONF_STATE]): cv.string,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def async_step_reconfigure_holidays(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-pick the tracked holidays after moving the instance to another place."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        current: dict[str, dict[str, Any]] = entry.options.get(CONF_HOLIDAYS, {})
        if user_input is not None:
            selected: list[str] = user_input[CONF_HOLIDAYS]
            if not selected:
                errors["base"] = "no_holidays_selected"
            else:
                new = self._new_instance_data
                # Holidays that exist in both places keep their customization.
                holidays = {name: current.get(name, {}) for name in selected}
                # Follow the place in the title only if it was never renamed.
                title = entry.title
                if title == default_title(entry.data[CONF_COUNTRY], entry.data[CONF_STATE]):
                    title = default_title(new[CONF_COUNTRY], new[CONF_STATE])
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=instance_unique_id(new[CONF_COUNTRY], new[CONF_STATE]),
                    title=title,
                    data={**entry.data, **new},
                    options={**entry.options, CONF_HOLIDAYS: holidays},
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOLIDAYS,
                    default=[name for name in current if name in self._holiday_list],
                ): cv.multi_select(self._holiday_list)
            }
        )
        return self.async_show_form(
            step_id="reconfigure_holidays", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: CalendarificConfigEntry) -> OptionsFlowWithReload:
        """Return the options flow handler."""
        return CalendarificOptionsFlowHandler()


class CalendarificOptionsFlowHandler(OptionsFlowWithReload):
    """Manage an existing instance: its holidays, its defaults, and per-holiday overrides.

    Reloads the entry automatically when the options change. Deliberately
    doesn't set self.config_entry in __init__ - recent HA versions populate it
    automatically before async_step_init runs, and assigning it here raises
    rather than just warning.
    """

    def __init__(self) -> None:
        """Initialize the flow."""
        self._holiday_list: list[str] = []
        self._selected_holiday = ""

    async def _fetch_holiday_list(self) -> list[str]:
        if not self._holiday_list:
            self._holiday_list = await _async_fetch_holiday_names(
                self.hass,
                self.config_entry.data[CONF_API_KEY],
                self.config_entry.data[CONF_COUNTRY],
                self.config_entry.data[CONF_STATE],
            )
        return self._holiday_list

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Menu: manage which holidays are tracked, edit instance defaults, or customize one holiday."""
        return self.async_show_menu(
            step_id="init", menu_options=["holidays", "defaults", "customize"]
        )

    async def async_step_holidays(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add or remove holidays. Removing one discards any override it had."""
        errors: dict[str, str] = {}
        current_holidays: dict[str, dict[str, Any]] = self.config_entry.options.get(
            CONF_HOLIDAYS, {}
        )
        try:
            holiday_list = await self._fetch_holiday_list()
        except CalendarificError as err:
            return self.async_abort(reason=_error_key(err))

        if user_input is not None:
            selected: list[str] = user_input[CONF_HOLIDAYS]
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

    async def async_step_defaults(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the instance-wide defaults every holiday inherits unless it has its own override."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_DEFAULTS: dict(user_input)},
            )

        current_defaults = self.config_entry.options.get(CONF_DEFAULTS, _hardcoded_defaults())
        schema = _holiday_settings_schema(current_defaults)
        return self.async_show_form(step_id="defaults", data_schema=schema)

    async def async_step_customize(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick which tracked holiday to override the instance defaults for."""
        current_holidays: dict[str, dict[str, Any]] = self.config_entry.options.get(
            CONF_HOLIDAYS, {}
        )
        if not current_holidays:
            return self.async_abort(reason="no_holidays_configured")

        if user_input is not None:
            self._selected_holiday = user_input["holiday"]
            return await self.async_step_customize_values()

        schema = vol.Schema({vol.Required("holiday"): vol.In(sorted(current_holidays.keys()))})
        return self.async_show_form(step_id="customize", data_schema=schema)

    async def async_step_customize_values(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set (or clear) this holiday's overrides on top of the instance defaults."""
        defaults: dict[str, Any] = self.config_entry.options.get(
            CONF_DEFAULTS, _hardcoded_defaults()
        )
        current_holidays: dict[str, dict[str, Any]] = self.config_entry.options.get(
            CONF_HOLIDAYS, {}
        )
        override = current_holidays.get(self._selected_holiday, {})

        if user_input is not None:
            values = dict(user_input)
            name = values.pop(CONF_NAME, "").strip()
            new_override: dict[str, Any]
            if values.pop(CONF_RESET_TO_DEFAULT, False):
                new_override = {}
            else:
                # Only keep values that actually differ from the instance defaults -
                # matching the default is equivalent to not overriding it. A custom
                # name has no instance default to compare against - blank means "use
                # the holiday's own name" rather than an override.
                new_override = {k: v for k, v in values.items() if v != defaults.get(k)}
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
