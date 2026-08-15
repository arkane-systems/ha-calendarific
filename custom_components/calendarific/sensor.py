""" Calendarific Sensor """
from datetime import datetime, date
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from .device import get_device_info

from .const import (
    ATTRIBUTION,
    CONF_ICON_NORMAL,
    CONF_ICON_TODAY,
    CONF_ICON_SOON,
    CONF_DATE_FORMAT,
    CONF_SOON,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_HOLIDAYS,
    CONF_DEFAULTS,
    DEFAULT_SOON,
    DEFAULT_ICON_SOON,
    DEFAULT_ICON_NORMAL,
    DEFAULT_ICON_TODAY,
    DEFAULT_DATE_FORMAT,
    DEFAULT_UNIT_OF_MEASUREMENT,
    DOMAIN,
    SENSOR_PLATFORM,
)

_LOGGER = logging.getLogger(__name__)

ATTR_DESCRIPTION = "description"
ATTR_DATE = "date"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up one sensor per holiday selected for this instance."""
    reader = hass.data[DOMAIN][entry.entry_id]["apiReader"]
    defaults = entry.options.get(CONF_DEFAULTS, {})
    holidays = entry.options.get(CONF_HOLIDAYS, {})
    async_add_entities(
        [
            # Sparse per-holiday overrides win; anything unset falls back to
            # the instance's defaults.
            calendarific(entry, holiday_name, {**defaults, **override}, reader)
            for holiday_name, override in holidays.items()
        ],
        True,
    )


class calendarific(Entity):
    def __init__(self, entry: ConfigEntry, holiday_name: str, config: dict, reader):
        """Initialize the sensor."""
        self._entry = entry
        self._holiday = holiday_name
        self._name = config.get("name") or holiday_name
        self._icon_normal = config.get(CONF_ICON_NORMAL, DEFAULT_ICON_NORMAL)
        self._icon_today = config.get(CONF_ICON_TODAY, DEFAULT_ICON_TODAY)
        self._icon_soon = config.get(CONF_ICON_SOON, DEFAULT_ICON_SOON)
        self._soon = config.get(CONF_SOON, DEFAULT_SOON)
        self._date_format = config.get(CONF_DATE_FORMAT, DEFAULT_DATE_FORMAT)
        self._unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT, DEFAULT_UNIT_OF_MEASUREMENT)
        self._icon = self._icon_normal
        # Scoped to this entry so the same holiday name in two different
        # instances (e.g. two countries) never collides.
        self._unique_id = f"{entry.entry_id}_{slugify(self._holiday)}"
        self._reader = reader
        self._description = self._reader.get_description(self._holiday)
        self._date = self._reader.get_date(self._holiday)
        if self._date == "-":
            self._attr_date = self._date
        else:
            self._attr_date = datetime.strftime(self._date,self._date_format)
        self._state = "unknown"

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DATE: self._attr_date,
            ATTR_DESCRIPTION: self._description,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        return self._icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information to group all of this instance's entities together."""
        return get_device_info(self._entry)

    async def async_added_to_hass(self):
        """Once the entity is added we should update to get the initial data loaded."""
        await super().async_added_to_hass()
        self.async_schedule_update_ha_state(True)
        self.hass.data[DOMAIN][self._entry.entry_id][SENSOR_PLATFORM][self.entity_id] = self

    async def async_will_remove_from_hass(self):
        """Deregister from the instance's sensor list when removed."""
        await super().async_will_remove_from_hass()
        _LOGGER.debug("Removing: %s" % (self._name))
        del self.hass.data[DOMAIN][self._entry.entry_id][SENSOR_PLATFORM][self.entity_id]

    async def async_update(self):
        await self.hass.async_add_executor_job(self._reader.update)
        self._description = self._reader.get_description(self._holiday)
        self._date = self._reader.get_date(self._holiday)
        if self._date == "-":
            self._state = "unknown"
            self._attr_date = self._date
            return
        self._attr_date = datetime.strftime(self._date,self._date_format)
        today = date.today()
        daysRemaining = 0
        if today < self._date:
            daysRemaining = (self._date - today).days
        elif today == self._date:
            daysRemaining = 0

        if daysRemaining == 0:
            self._icon = self._icon_today
        elif daysRemaining <= self._soon:
            self._icon = self._icon_soon
        else:
            self._icon = self._icon_normal
        self._state = daysRemaining
