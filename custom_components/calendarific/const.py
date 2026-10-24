""" Constants """
# Base component constants
DOMAIN = "calendarific"
VERSION = "0.17.0"
ISSUE_URL = "https://github.com/arkane-systems/ha-calendarific/issues"
ATTRIBUTION = "Data provided by calendarific.com"

# Device information
CONFIGURATION_URL = "https://calendarific.com/account"
DEVICE_MANUFACTURER = "Calendarific"
DEVICE_MODEL = "Holiday Calendar"

ATTR_DATE = "date"
ATTR_DAYS = "days"
ATTR_DESCRIPTION = "description"

# Config entry schema version (distinct from the integration version).
# Minor 2 added the per-instance unique ID; minor 3 dropped the unit setting.
CONFIG_ENTRY_VERSION = 1
CONFIG_ENTRY_MINOR_VERSION = 3

# Configuration
CONF_ENABLED = "enabled"
CONF_ICON_NORMAL = "icon_normal"
CONF_ICON_TODAY = "icon_today"
CONF_ICON_SOON = "icon_soon"
CONF_DATE_FORMAT = "date_format"
CONF_SOON = "days_as_soon"
CONF_API_KEY = "api_key"
CONF_COUNTRY = "country"
CONF_STATE = "state"
CONF_HOLIDAYS = "holidays"
CONF_DEFAULTS = "defaults"

# Defaults
DEFAULT_ICON_NORMAL = "mdi:calendar-blank"
DEFAULT_ICON_TODAY = "mdi:calendar-star"
DEFAULT_ICON_SOON = "mdi:calendar"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SOON = 3
