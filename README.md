# Calendarific
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/cerebrate/Calendarific)](https://github.com/cerebrate/Calendarific/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/cerebrate/Calendarific)
[![GitHub](https://img.shields.io/github/license/cerebrate/Calendarific)](LICENSE)

[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://github.com/cerebrate/Calendarific/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/cerebrate/Calendarific)](https://github.com/cerebrate/Calendarific/issues)

This is a post-abandonment reboot of the Calendarific integration, originally created and maintained by @pinkywafer. The original repository can be found at [pinkywafer/Calendarific](https://github.com/pinkywafer/Calendarific).

---

The _Calendarific_ component is a Home Assistant custom sensor which counts down to public holidays and observances, by querying the [Calendarific](http://www.calendarific.com/) API.

State Returned:
* The number of days remaining to the next occurance.

Attributes (both are provided by the Calendarific API):
* **date:**  The next date of the holiday (formatted by date_format configuration option if set)
* **description:** The description of the holiday.

Additionally, the component provides a Home Assistant calendar (after at least one sensor has been configured) which lists the upcoming configured holidays.  The calendar event summary is the name of the holiday and the description is the description of the holiday provided by the Calendarific API.

## Table of Contents

* [Installation](#installation)
  + [Manual Installation](#manual-installation)
* [Platform Configuration](#platform-configuration)
  + [Platform Configuration Parameters](#platform-configuration-parameters)
* [Sensor Configuration](#sensor-configuration)
  + [Sensor Configuration Parameters](#sensor-configuration-parameters)

## Installation

### MANUAL INSTALLATION

1. Download the `calendarific.zip` file from the 
   [latest release](https://github.com/cerebrate/Calendarific/releases/latest).
2. Unpack the release and copy the `custom_components/calendarific` directory
   into the `custom_components` directory of your Home Assistant
   installation.
3. Configure the `calendarific` platform
4. Restart Home Assistant.
5. Configure sensors either in the configuration.yaml or by using the integrations page

## Platform Configuration

You will need an API key from Calendarific. Go to the [sign up page](https://calendarific.com/signup) and open a new account.  A free tier account is limited to 1000 API calls per month.  This integration will make two calls per day (and two on Home Assistant start)

**The Calendarific platform MUST be configured in the configuration.yaml file.**

```yaml
# Example configuration.yaml platform entry
calendarific:
  api_key: YOUR_API_KEY
  country: US
  state: US-KS
```

### Platform configuration parameters
|Attribute |Optional|Description
|:----------|----------|------------
| `api_key` | No | your api key from calendarific.com
| `country` | No | your country code ([here is a list of supported countries](https://calendarific.com/supported-countries))
| `state` | Yes | your state code (ISO 3166-2 subdivision code) [[USA](https://en.wikipedia.org/wiki/ISO_3166-2:US)] [[UK](https://en.wikipedia.org/wiki/ISO_3166-2:GB)]

_Note that the state code is for the country in the UK (counties are not supported) or the state in the US._ If omitted, only national holidays will be displayed.

## Sensor Configuration

Individual sensors can be configured using the config flow or in `configuration.yaml`:

### Config Flow

In Configuration/Integrations click on the + button, select Calendarific and configure the options on the form (The available holidays will automatically appear in the list if the platform was configured correctly in the above step).

### configuration.yaml

Add a `calendarific` sensor in your `configuration.yaml`. The following example adds two sensors - New Year's Day and Christmas Day. _(Note that these must be entered EXACTLY as they are on the Calendarific server.)_

```yaml
# Example configuration.yaml sensor entry
sensor:
  - platform: calendarific
    holiday: New Year's Day
  - platform: calendarific
    holiday: Christmas Day
```

### Sensor Configuration Parameters
|Attribute |Optional|Description
|:----------|----------|------------
| `holiday` | No | Name of the holiday provided by calendarific api
| `name` | Yes | Friendly name, defaulting to the holiday name
| `icon_normal` | Yes | Default iconm defaulting to `mdi:calendar-blank`
| `icon_today` | Yes | Icon if the holiday is today, defaulting to `mdi:calendar-star`
| `days_as_soon` | Yes | Days in advance to display the icon defined in `icon_soon`, defaulting to 3
| `icon_soon` | Yes | Icon if the holiday is 'soon', defaulting to `mdi:calendar`
| `date_format` | Yes | formats the returned datem defaulting to '%Y-%m-%d' (_For reference, see [http://strftime.org/](http://strftime.org/))._
