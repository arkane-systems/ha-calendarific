# Calendarific
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/cerebrate/Calendarific)](https://github.com/cerebrate/Calendarific/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/cerebrate/Calendarific)
[![GitHub](https://img.shields.io/github/license/cerebrate/Calendarific)](LICENSE)

[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://github.com/cerebrate/Calendarific/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/cerebrate/Calendarific)](https://github.com/cerebrate/Calendarific/issues)

This is a post-abandonment reboot of the Calendarific integration, originally created and maintained by @pinkywafer. The original repository can be found at [pinkywafer/Calendarific](https://github.com/pinkywafer/Calendarific).

---

The _Calendarific_ component is a Home Assistant custom integration which counts down to public holidays and observances, by querying the [Calendarific](http://www.calendarific.com/) API.

Each **instance** you configure tracks one country/state combination (e.g. "US - KS" or "GB") and can track any number of holidays within it. All of an instance's holiday sensors are grouped under a single device, and the instance gets its own calendar entity listing its selected holidays. You can configure any number of instances side by side - for example one for US/US-KS and another for GB - each with its own device and calendar.

State Returned (per holiday sensor):
* The number of days remaining to the next occurrence.

Attributes (both are provided by the Calendarific API):
* **date:**  The next date of the holiday (formatted by date_format configuration option if set)
* **description:** The description of the holiday.

## Table of Contents

* [Installation](#installation)
  + [Manual Installation](#manual-installation)
* [Setting up an instance](#setting-up-an-instance)
* [Managing holidays](#managing-holidays)
* [Sensor Configuration Parameters](#sensor-configuration-parameters)
* [Translations](#translations)

## Installation

### MANUAL INSTALLATION

1. Download the `calendarific.zip` file from the 
   [latest release](https://github.com/cerebrate/Calendarific/releases/latest).
2. Unpack the release and copy the `custom_components/calendarific` directory
   into the `custom_components` directory of your Home Assistant
   installation.
3. Restart Home Assistant.
4. Set up one or more instances via the Integrations page (see below).

## Setting up an instance

You will need an API key from Calendarific. Go to the [sign up page](https://calendarific.com/signup) and open a new account. A free tier account is limited to 1000 API calls per month. Each instance makes two calls per day (and two on Home Assistant start).

In Settings/Devices & Services click **+ Add Integration**, select **Calendarific**, and:

1. Enter a friendly name for the instance (optional - one is generated from the country/state if left blank), your API key, country code, and state/subdivision code.
   * Country codes: [list of supported countries](https://calendarific.com/supported-countries).
   * State codes are ISO 3166-2 subdivision codes ([USA](https://en.wikipedia.org/wiki/ISO_3166-2:US), [UK](https://en.wikipedia.org/wiki/ISO_3166-2:GB); UK counties are not supported). Leave blank to see only national holidays.
2. Set the instance's default sensor settings (icons, "soon" threshold, date format, unit of measurement) - these apply to every holiday in the instance unless you override them for a specific one later.
3. Choose which of the available holidays to create sensors for, from the list fetched live from Calendarific for that country/state.

This creates one device (grouping every holiday sensor for that instance) and one calendar entity listing them.

To track a different country or state as well, just add another instance the same way - each is independent, with its own device, calendar, and defaults.

## Managing holidays

Find the instance on the Integrations page and click **Configure** to:

* **Add or remove holidays** - re-opens the holiday picker, pre-selected with the holidays currently tracked. Removing a holiday also discards any customization it had.
* **Edit instance defaults** - changes the settings every holiday in this instance inherits, unless it has its own override.
* **Customize a specific holiday** - pick one tracked holiday and set its own friendly name, icons/date format/etc., overriding the instance defaults just for it. The form shows that holiday's current *effective* settings (its override, or the instance default if it has none). Check **Reset to instance default** to discard the override and go back to inheriting - any other changes made in the same form are ignored when this is checked. Setting a field back to match the instance default has the same effect for that one field; for the friendly name, leaving it blank has the same effect.

  A custom friendly name only changes the entity's *display* name - it won't rename its `entity_id`, since Home Assistant assigns that once from the name at entity creation and never renames it automatically afterward. To also change the `entity_id`, use that entity's own settings dialog (Settings → Devices & Services → Entities).

## Sensor Configuration Parameters

Each instance has its own defaults for these settings (set during setup, editable afterward), which individual holidays can override:

|Attribute |Built-in fallback
|:----------|------------
| `icon_normal` | `mdi:calendar-blank`
| `icon_today` | `mdi:calendar-star`
| `days_as_soon` | 3
| `icon_soon` | `mdi:calendar`
| `date_format` | `%Y-%m-%d` (_For reference, see [http://strftime.org/](http://strftime.org/))_
| `unit_of_measurement` | `days`

## Translations

`en.json` (English) is the source of truth for the config/options flow text. The other language files under `custom_components/calendarific/translations/` are community-contributed and may lag behind or contain imperfect phrasing - corrections, updates, and additional languages are all welcome as pull requests.
