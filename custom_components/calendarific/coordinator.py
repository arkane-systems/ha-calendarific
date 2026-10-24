"""Data update coordinator for Calendarific."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    CalendarificAuthError,
    CalendarificClient,
    CalendarificError,
    HolidayData,
)
from .const import CONF_API_KEY, CONF_COUNTRY, CONF_STATE, DOMAIN

_LOGGER = logging.getLogger(__name__)

type CalendarificConfigEntry = ConfigEntry[CalendarificCoordinator]

# Holiday dates for a year don't change, so one fetch a day is plenty.
REFRESH_INTERVAL = timedelta(days=1)
# Calendarific counts failed requests against the monthly quota (500 on the
# free plan), so retry an outage slowly.
RETRY_INTERVAL = timedelta(hours=3)


class CalendarificCoordinator(DataUpdateCoordinator[HolidayData]):
    """Fetches this year's and next year's holidays for one country/state."""

    config_entry: CalendarificConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CalendarificConfigEntry) -> None:
        """Initialize the coordinator for a config entry."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=REFRESH_INTERVAL,
        )
        self._client = CalendarificClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._country: str = entry.data[CONF_COUNTRY]
        self._state: str = entry.data[CONF_STATE]
        self._serving_stale = False

    async def _async_setup(self) -> None:
        """Roll sensor day counts over at local midnight without any API call."""
        self.config_entry.async_on_unload(
            async_track_time_change(
                self.hass, self._async_handle_midnight, hour=0, minute=0, second=0
            )
        )

    @callback
    def _async_handle_midnight(self, _now: datetime) -> None:
        """Recompute entity states for the new day, refetching if the year changed."""
        today = dt_util.now().date()
        if self.data is not None and today.year + 1 not in self.data.by_year:
            self.config_entry.async_create_task(self.hass, self.async_request_refresh())
        self.async_update_listeners()

    async def _async_update_data(self) -> HolidayData:
        """Fetch fresh holidays, falling back to the cache through an outage."""
        today = dt_util.now().date()
        try:
            data = await self._async_fetch(today.year)
        except CalendarificAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except CalendarificError as err:
            return self._handle_fetch_failure(err, today)

        if self._serving_stale:
            self._serving_stale = False
            _LOGGER.info("Calendarific is reachable again; holiday data refreshed")
        self.update_interval = REFRESH_INTERVAL
        return data

    async def _async_fetch(self, year: int) -> HolidayData:
        current = await self._client.async_get_holidays(self._country, year, self._state)
        following = await self._client.async_get_holidays(
            self._country, year + 1, self._state
        )
        return HolidayData.from_lists({year: current, year + 1: following})

    def _handle_fetch_failure(self, err: CalendarificError, today: date) -> HolidayData:
        """Keep serving cached data if it still covers today, else fail the update."""
        self.update_interval = RETRY_INTERVAL
        if self.data is not None and self.data.covers(today):
            if not self._serving_stale:
                self._serving_stale = True
                _LOGGER.warning(
                    "Unable to refresh holidays from Calendarific (%s); "
                    "continuing with cached data and retrying every %s",
                    err,
                    RETRY_INTERVAL,
                )
            return self.data
        self._serving_stale = False
        raise UpdateFailed(f"Error fetching holidays from Calendarific: {err}") from err
