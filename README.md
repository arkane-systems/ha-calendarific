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
2. Choose which of the available holidays to create sensors for, from the list fetched live from Calendarific for that country/state.

This creates one device (grouping every holiday sensor for that instance) and one calendar entity listing them.

To track a different country or state as well, just add another instance the same way - each is independent, with its own device and calendar.

## Managing holidays

To add or remove holidays on an existing instance later, find it on the Integrations page and click **Configure**. This re-opens the holiday picker, pre-selected with the holidays currently tracked; changing the selection adds or removes the corresponding sensors.

## Sensor Configuration Parameters

Holiday sensors are created with the following defaults, applied to every holiday selected in an instance:

|Attribute |Default
|:----------|------------
| `icon_normal` | `mdi:calendar-blank`
| `icon_today` | `mdi:calendar-star`
| `days_as_soon` | 3
| `icon_soon` | `mdi:calendar`
| `date_format` | `%Y-%m-%d` (_For reference, see [http://strftime.org/](http://strftime.org/))_
| `unit_of_measurement` | `days`
