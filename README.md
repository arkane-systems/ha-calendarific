# <img src="custom_components/calendarific/brand/icon.png" alt="" width="40" align="absmiddle"> Calendarific
[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/arkane-systems/ha-calendarific)](https://github.com/arkane-systems/ha-calendarific/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/arkane-systems/ha-calendarific)
[![GitHub](https://img.shields.io/github/license/arkane-systems/ha-calendarific)](LICENSE)

[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://github.com/arkane-systems/ha-calendarific/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/arkane-systems/ha-calendarific)](https://github.com/arkane-systems/ha-calendarific/issues)

This is a post-abandonment reboot of the Calendarific integration, originally created and maintained by @pinkywafer. The original repository can be found at [pinkywafer/Calendarific](https://github.com/pinkywafer/Calendarific).

> **Upgrading from a pre-0.15 release?** 0.15 is a breaking rearchitecture (per-instance config entries, multi-holiday setup) and there's no migration path from the old one-entry-per-holiday config entries. After upgrading, remove your existing Calendarific integration entries under Settings → Devices & Services and set them up again from scratch.

> **Upgrading from 0.16 to 1.0?** Your instances migrate automatically. Home Assistant 2025.8 or newer is now required. Holiday sensors always use days as their unit (the *unit of measurement* setting is gone), a Next Holiday sensor is now named after its instance (for example "Home Next holiday"), and Home Assistant now removes the sensor of any holiday you stop tracking.

---

The _Calendarific_ component is a Home Assistant custom integration which counts down to public holidays and observances, by querying the [Calendarific](http://www.calendarific.com/) API. It requires Home Assistant 2025.8 or newer and an internet connection.

Each **instance** you configure tracks one country/state combination (e.g. "US - KS" or "GB") and can track any number of holidays within it. All of an instance's holiday sensors are grouped under a single device, and the instance gets its own calendar entity listing its selected holidays. It also gets a **Next Holiday** sensor reporting whichever of its tracked holidays is coming up soonest. You can configure any number of instances side by side - for example one for US/US-KS and another for GB - each with its own device, calendar, and next-holiday sensor.

## Table of Contents

* [What you get](#what-you-get)
* [Use cases](#use-cases)
* [Installation](#installation)
* [Setting up an instance](#setting-up-an-instance)
* [Configuration options](#configuration-options)
* [Holidays Calendarific stops listing](#holidays-calendarific-stops-listing)
* [Changing an instance's account or location](#changing-an-instances-account-or-location)
* [How data is updated](#how-data-is-updated)
* [Examples](#examples)
* [Known limitations](#known-limitations)
* [Troubleshooting](#troubleshooting)
* [Removing the integration](#removing-the-integration)
* [Translations](#translations)

## What you get

Each instance creates one device (named after the instance) holding these entities. The integration has no actions, triggers or conditions of its own.

| Entity | State | Attributes |
|:-------|:------|:-----------|
| **A sensor per tracked holiday**, named after the holiday (for example `sensor.christmas_day`) | The number of days until the holiday's next occurrence, `0` on the day itself. The unit is always days (the *duration* device class), so Home Assistant can show it in your language or convert it from the entity's settings. *Unknown* if Calendarific doesn't list the holiday. | **date**: the next date, formatted by the *date format* setting. **description**: the description Calendarific gives the holiday. |
| **Next Holiday** sensor, named "*instance name* Next holiday" | The name of whichever tracked holiday is coming up soonest (its custom name, if it has one). | **days**: the days remaining until it. |
| **Calendar**, named after the instance | The tracked holidays as all-day events. | Standard calendar attributes for the current or next event. |

A holiday sensor's icon changes with the distance to the holiday: the *normal* icon, then the *soon* icon within the "soon" threshold, then the *today* icon on the day.

## Use cases

* Turn on a "bank holiday" lighting or heating schedule, or silence the weekday alarm, on public holidays.
* Send yourself a reminder a week, a day or a few hours before a holiday so you can buy cards and gifts.
* Show a countdown, or the name and date of the next holiday, on a dashboard.
* Keep holidays for the country where family live alongside your own, using one instance for each.
* Put the holidays on a Home Assistant calendar card or use them as calendar triggers.

## Installation

### HACS

Calendarific is in the HACS default store:

1. In HACS, search for **Calendarific** and click **Download**.
2. Restart Home Assistant.
3. Set up one or more instances via the Integrations page (see below).

### Manual installation

1. Download this repository - either as a zip via GitHub's **Code → Download ZIP** button, or from the source code archive attached to a specific [release](https://github.com/arkane-systems/ha-calendarific/releases).
2. Copy the `custom_components/calendarific` directory from the download
   into the `custom_components` directory of your Home Assistant
   installation.
3. Restart Home Assistant.
4. Set up one or more instances via the Integrations page (see below).

## Setting up an instance

You will need an API key from Calendarific. Go to the [sign up page](https://calendarific.com/signup) and open a new account. A free tier account is limited to 500 API calls per month, and failed requests count too. Each instance makes two calls per day, plus two whenever Home Assistant starts or the instance is reloaded (for example after you change its holidays). See [How data is updated](#how-data-is-updated).

In Settings/Devices & Services click **+ Add Integration**, select **Calendarific**, and work through three steps.

**1. The instance**

| Field | Description |
|:------|:------------|
| Friendly name | Optional. A name for the instance, used for its device, calendar and Next Holiday sensor. If left blank, one is generated from the country and state, such as "Calendarific (US - KS)". |
| API key | The API key from your Calendarific account. |
| Country code | The two-letter ISO 3166-1 code, for example `US` or `GB`. See the [list of supported countries](https://calendarific.com/supported-countries). |
| State/subdivision code | Optional. An ISO 3166-2 subdivision code for regional holidays ([USA](https://en.wikipedia.org/wiki/ISO_3166-2:US), [UK](https://en.wikipedia.org/wiki/ISO_3166-2:GB); UK counties are not supported). Leave blank to see only national holidays. |

Each country and state can be added to only one instance. The key is checked as you continue, and a rejected key, a quota that has run out or an unreachable Calendarific is reported on the form.

**2. The instance defaults** - the [sensor settings](#sensor-settings) every holiday in the instance uses unless you override them for a specific one later.

**3. The holidays** - choose which of the available holidays to create sensors for, from the list fetched live from Calendarific for that country and state.

This creates one device (grouping every holiday sensor for that instance), one calendar entity and one Next Holiday sensor. To track a different country or state as well, just add another instance the same way - each is independent, with its own device, calendar, and defaults.

## Configuration options

Find the instance on the Integrations page and click **Configure**. Saving any of these reloads the instance.

| Option | What it does |
|:-------|:-------------|
| **Add or remove holidays** | Re-opens the holiday picker, pre-selected with the holidays currently tracked, and needs at least one. Removing a holiday discards any customization it had and removes its sensor. |
| **Edit instance defaults** | Changes the [sensor settings](#sensor-settings) every holiday in this instance inherits, unless it has its own override. |
| **Customize a specific holiday** | Pick one tracked holiday and give it its own *friendly name* and any of the sensor settings, overriding the instance defaults for just that holiday. The form shows that holiday's current *effective* settings (its override, or the instance default if it has none). Check **Reset to instance default** to discard the override and go back to inheriting - any other changes made in the same form are ignored when this is checked. Setting a field back to match the instance default has the same effect for that one field; for the friendly name, leaving it blank has the same effect. |

A custom friendly name only changes the entity's *display* name - it won't rename its `entity_id`, since Home Assistant assigns that once from the name at entity creation and never renames it automatically afterward. To also change the `entity_id`, use that entity's own settings dialog (Settings → Devices & Services → Entities).

### Sensor settings

Each holiday sensor's icons, "soon" threshold and date format are resolved from three layers, each falling back to the one below it if unset:

1. **Per-holiday override** - set via Configure → Customize a specific holiday. Only stored for settings that differ from the instance default.
2. **Instance default** - set at instance setup, editable via Configure → Edit instance defaults. Applies to every holiday in the instance unless overridden.
3. **Built-in fallback** - pre-fills the instance defaults form the first time you set one up; listed below.

| Setting | Description | Built-in fallback |
|:--------|:------------|:------------------|
| Default icon | Shown while the holiday is further away than the "soon" threshold. | `mdi:calendar-blank` |
| Icon when a holiday is today | Shown on the day of the holiday. | `mdi:calendar-star` |
| Number of days to consider a holiday "soon" | A holiday this many days away or fewer is "soon". | 3 |
| Icon when a holiday is soon | Shown while the holiday is "soon". | `mdi:calendar` |
| Date format | How the sensor's `date` attribute is written, in Python strftime syntax (see [strftime.org](http://strftime.org/)). | `%Y-%m-%d` |

## Holidays Calendarific stops listing

Home Assistant keeps a tracked holiday's sensor up to date only while Calendarific lists a holiday by that name for your country and state. If it disappears (for example because it was renamed), the sensor shows *unknown* and a repair appears under Settings → System → Repairs offering to stop tracking it. Confirming removes the holiday from the instance; if it was renamed, add the new name from **Configure** afterwards.

A holiday that Calendarific still lists, but which has already passed this year and isn't listed for next year, also shows *unknown* until it is, and does not raise a repair.

## Changing an instance's account or location

Find the instance on the Integrations page, open its three-dot menu and choose **Reconfigure** to change its API key, country or state.

* Changing only the API key (or re-typing the same country and state) updates the instance in place.
* Moving the instance to a different country or state asks you to choose its holidays again. Holidays that are also available at the new location are pre-selected and keep any customization you gave them; the others are dropped. If the instance still had its generated name (such as "Calendarific (US)"), the name follows the new location; a name you chose yourself is kept.
* Each country and state can be added to only one instance, so you can't move an instance onto a location another instance already tracks.

If Calendarific rejects your API key (for example because it was revoked or your subscription expired), Home Assistant asks you to enter a new one.

## How data is updated

* Each instance fetches the holidays for **this year and next year** from Calendarific: two requests, once a day, plus two whenever Home Assistant starts or the instance is reloaded. Changing an instance's options reloads it.
* The sensors and calendar are worked out from that stored data, so they make no requests of their own. Day counts roll over at midnight in the time zone configured in Home Assistant (Settings → System → General), and a new year triggers a fresh fetch.
* **If Calendarific can't be reached**, the entities keep working from the data already fetched - holiday dates don't change - and Home Assistant logs a single warning. The integration retries every three hours (slowly, because failed requests count against your monthly quota) and logs once when Calendarific is reachable again. The entities only become unavailable if the stored data no longer covers the current year, which takes more than a year of continuous failure.
* If Calendarific rejects the API key, the entities become unavailable and Home Assistant asks you to enter a new key.

## Examples

The entity IDs below depend on your instance and holiday names; adjust them to match yours. A Next Holiday sensor's ID starts with the instance's name, so an instance called "Home" has `sensor.home_next_holiday` and `calendar.home`.

**Notify on the day of a holiday**

```yaml
automation:
  - alias: "Christmas Day"
    triggers:
      - trigger: state
        entity_id: sensor.christmas_day
        to: "0"
    actions:
      - action: notify.notify
        data:
          message: "Merry Christmas!"
```

**Remind yourself a week ahead** - the same trigger with `to: "7"`.

**Remind yourself at 6 pm the evening before, using the calendar**

```yaml
automation:
  - alias: "Holiday tomorrow"
    triggers:
      - trigger: calendar
        event: start
        entity_id: calendar.home
        offset: "-6:00:00"
    actions:
      - action: notify.notify
        data:
          message: "Tomorrow is {{ trigger.calendar_event.summary }}."
```

All-day events start at midnight, so the offset of minus six hours fires at 6 pm the day before.

**Show the next holiday in a template or dashboard card**

```jinja
{{ states('sensor.home_next_holiday') }} is in {{ state_attr('sensor.home_next_holiday', 'days') }} days
```

## Known limitations

* **Holidays are matched by name.** Calendarific's names are in English and are what the integration tracks. If Calendarific renames a holiday, the old sensor goes *unknown* and a repair is raised (see above).
* **Quota.** The free plan allows 500 requests a month and failed requests count. Each instance uses about 60 a month, plus two for every restart or reload, so many instances on one key or frequent restarts can run it down.
* **One instance per country and state.** A second instance for the same place is refused.
* **The calendar only covers the stored years** - the current year and the next. Dates further back or ahead show nothing, and a holiday that has passed this year and isn't listed for next year shows *unknown* on its sensor.
* **Custom names don't change entity IDs**, and renaming an instance doesn't rename its device or calendar until the next reload or restart (or rename them from their own settings).
* **Only the data Calendarific provides.** Dates, descriptions and which holidays exist are Calendarific's; the integration reports them as given.
* **YAML configuration is not supported.** Everything is set up through the UI.

## Troubleshooting

**Setup says the API key was rejected** - check the key on your Calendarific account and that your subscription is active (an expired one is also reported this way). If a key stops working later, Home Assistant raises a re-authentication prompt on the instance.

**Setup says the monthly request limit has been reached** - the free plan allows 500 requests a month. Wait for the month to roll over or upgrade the plan.

**Setup says it could not reach Calendarific** - check Home Assistant's internet connection and [Calendarific's status](https://calendarific.com), then try again.

**"No holidays found"** - Calendarific returned nothing for that country and state. Check the [country code](https://calendarific.com/supported-countries), and try leaving the state blank to see the national holidays.

**A holiday sensor shows *unknown*** - Calendarific no longer lists a holiday by that name (look for a repair under Settings → System → Repairs), or it has passed this year and isn't listed for next year.

**Sensors change at the wrong time of day** - they roll over at midnight in the time zone set in Settings → System → General, not the time zone of the machine Home Assistant runs on.

**Need to see what the integration is doing** - enable debug logging by adding this to `configuration.yaml`, or from the integration's page with **Enable debug logging**:

```yaml
logger:
  logs:
    custom_components.calendarific: debug
```

**Reporting a problem** - download the instance's diagnostics from the three-dot menu on the Integrations page (**Download diagnostics**) and attach them to a [GitHub issue](https://github.com/arkane-systems/ha-calendarific/issues). The API key is redacted; the file includes the country, state, your options and when each tracked holiday next falls.

## Removing the integration

1. Under Settings → Devices & Services, open Calendarific, click the three-dot menu on the instance you want to remove and choose **Delete**. This removes the instance's device, its sensors, its calendar and any repairs it raised. Other instances are untouched. Repeat for each instance.
2. If you installed with HACS, open Calendarific in HACS, choose **Remove** from its three-dot menu, and restart Home Assistant. If you installed manually, delete the `custom_components/calendarific` directory and restart.
3. Optionally, delete the API key from your Calendarific account.

## Translations

`strings.json` is the source of truth for the config/options flow text, and `translations/en.json` (English) is generated from it. The other language files under `custom_components/calendarific/translations/` (currently Croatian, Norwegian Bokmål and Dutch) were translated from the English text and have not all been reviewed by native speakers, so they may contain imperfect phrasing - corrections and additional languages are very welcome as pull requests. A language file must contain every string in `en.json` with the same `{placeholders}`; the test suite checks this, so use `en.json` as the template.
