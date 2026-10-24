# <img src="custom_components/calendarific/brand/icon.png" alt="" width="40" align="absmiddle"> Calendarific
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub release (latest by date)](https://img.shields.io/github/v/release/arkane-systems/ha-calendarific)](https://github.com/arkane-systems/ha-calendarific/releases)
![GitHub Release Date](https://img.shields.io/github/release-date/arkane-systems/ha-calendarific)
[![GitHub](https://img.shields.io/github/license/arkane-systems/ha-calendarific)](LICENSE)

[![Maintenance](https://img.shields.io/badge/Maintained%3F-Yes-brightgreen.svg)](https://github.com/arkane-systems/ha-calendarific/graphs/commit-activity)
[![GitHub issues](https://img.shields.io/github/issues/arkane-systems/ha-calendarific)](https://github.com/arkane-systems/ha-calendarific/issues)

This is a post-abandonment reboot of the Calendarific integration, originally created and maintained by @pinkywafer. The original repository can be found at [pinkywafer/Calendarific](https://github.com/pinkywafer/Calendarific).

> **Upgrading from a pre-0.15 release?** 0.15 is a breaking rearchitecture (per-instance config entries, multi-holiday setup) and there's no migration path from the old one-entry-per-holiday config entries. After upgrading, remove your existing Calendarific integration entries under Settings → Devices & Services and set them up again from scratch.

---

The _Calendarific_ component is a Home Assistant custom integration which counts down to public holidays and observances, by querying the [Calendarific](http://www.calendarific.com/) API.

Each **instance** you configure tracks one country/state combination (e.g. "US - KS" or "GB") and can track any number of holidays within it. All of an instance's holiday sensors are grouped under a single device, and the instance gets its own calendar entity listing its selected holidays. It also gets a **Next Holiday** sensor reporting whichever of its tracked holidays is coming up soonest. You can configure any number of instances side by side - for example one for US/US-KS and another for GB - each with its own device, calendar, and next-holiday sensor.

State Returned (per holiday sensor):
* The number of days remaining to the next occurrence. The unit is always days (the sensor has the Home Assistant *duration* device class), so Home Assistant can display it in your language or convert it to another time unit from the entity's settings.

Attributes (both are provided by the Calendarific API):
* **date:**  The next date of the holiday (formatted by date_format configuration option if set)
* **description:** The description of the holiday.

State Returned (Next Holiday sensor):
* The name of whichever tracked holiday in this instance is coming up soonest (its custom friendly name, if it has one).

Attributes:
* **days:** The number of days remaining until that holiday.

## Table of Contents

* [Installation](#installation)
  + [HACS](#hacs)
  + [Manual Installation](#manual-installation)
* [Setting up an instance](#setting-up-an-instance)
* [Managing holidays](#managing-holidays)
* [Holidays Calendarific stops listing](#holidays-calendarific-stops-listing)
* [Changing an instance's account or location](#changing-an-instances-account-or-location)
* [Sensor Settings Reference](#sensor-settings-reference)
* [Translations](#translations)

## Installation

### HACS

This integration isn't yet in HACS's default store, so for now it needs to be added as a custom repository:

1. In HACS, open **Integrations**, click the three-dot menu in the top right corner, and select **Custom repositories**.
2. Add `https://github.com/arkane-systems/ha-calendarific` as the repository, with category **Integration**.
3. Find **Calendarific** in HACS and click **Download**.
4. Restart Home Assistant.
5. Set up one or more instances via the Integrations page (see below).

### MANUAL INSTALLATION

1. Download this repository - either as a zip via GitHub's **Code → Download ZIP** button, or from the source code archive attached to a specific [release](https://github.com/arkane-systems/ha-calendarific/releases).
2. Copy the `custom_components/calendarific` directory from the download
   into the `custom_components` directory of your Home Assistant
   installation.
3. Restart Home Assistant.
4. Set up one or more instances via the Integrations page (see below).

## Setting up an instance

You will need an API key from Calendarific. Go to the [sign up page](https://calendarific.com/signup) and open a new account. A free tier account is limited to 500 API calls per month, and failed requests count too. Each instance makes two calls per day, plus two whenever Home Assistant starts or the instance is reloaded (for example after you change its holidays). If Calendarific can't be reached, the integration keeps using the holidays it last fetched and retries every few hours.

In Settings/Devices & Services click **+ Add Integration**, select **Calendarific**, and:

1. Enter a friendly name for the instance (optional - one is generated from the country/state if left blank), your API key, country code, and state/subdivision code.
   * Country codes: [list of supported countries](https://calendarific.com/supported-countries).
   * State codes are ISO 3166-2 subdivision codes ([USA](https://en.wikipedia.org/wiki/ISO_3166-2:US), [UK](https://en.wikipedia.org/wiki/ISO_3166-2:GB); UK counties are not supported). Leave blank to see only national holidays.
2. Set the instance's default sensor settings (icons, "soon" threshold, date format) - these apply to every holiday in the instance unless you override them for a specific one later.
3. Choose which of the available holidays to create sensors for, from the list fetched live from Calendarific for that country/state.

This creates one device (grouping every holiday sensor for that instance) and one calendar entity listing them.

To track a different country or state as well, just add another instance the same way - each is independent, with its own device, calendar, and defaults.

## Managing holidays

Find the instance on the Integrations page and click **Configure** to:

* **Add or remove holidays** - re-opens the holiday picker, pre-selected with the holidays currently tracked. Removing a holiday also discards any customization it had.
* **Edit instance defaults** - changes the settings every holiday in this instance inherits, unless it has its own override.
* **Customize a specific holiday** - pick one tracked holiday and set its own friendly name, icons/date format/etc., overriding the instance defaults just for it. The form shows that holiday's current *effective* settings (its override, or the instance default if it has none). Check **Reset to instance default** to discard the override and go back to inheriting - any other changes made in the same form are ignored when this is checked. Setting a field back to match the instance default has the same effect for that one field; for the friendly name, leaving it blank has the same effect.

  A custom friendly name only changes the entity's *display* name - it won't rename its `entity_id`, since Home Assistant assigns that once from the name at entity creation and never renames it automatically afterward. To also change the `entity_id`, use that entity's own settings dialog (Settings → Devices & Services → Entities).

## Holidays Calendarific stops listing

Home Assistant keeps a tracked holiday's sensor up to date only while Calendarific lists a holiday by that name for your country and state. If it disappears (for example because it was renamed), the sensor shows *unknown* and a repair appears under Settings → System → Repairs offering to stop tracking it. Confirming removes the holiday from the instance; if it was renamed, add the new name from **Configure** afterwards.

Stopping tracking a holiday, by either route, also removes its sensor entity.

## Changing an instance's account or location

Find the instance on the Integrations page, open its three-dot menu and choose **Reconfigure** to change its API key, country or state.

* Changing only the API key (or re-typing the same country and state) updates the instance in place.
* Moving the instance to a different country or state asks you to choose its holidays again. Holidays that are also available at the new location are pre-selected and keep any customization you gave them; the others are dropped. If the instance still had its generated name (such as "Calendarific (US)"), the name follows the new location; a name you chose yourself is kept.
* Each country and state can be added to only one instance, so you can't move an instance onto a location another instance already tracks.

If Calendarific rejects your API key (for example because it was revoked or your subscription expired), Home Assistant asks you to enter a new one.

## Sensor Settings Reference

Each holiday sensor's icons, "soon" threshold and date format are resolved from three layers, each falling back to the one below it if unset:

1. **Per-holiday override** - set via Configure → Customize a specific holiday. Only stored for settings that differ from the instance default.
2. **Instance default** - set at instance setup, editable via Configure → Edit instance defaults. Applies to every holiday in the instance unless overridden.
3. **Built-in fallback** - pre-fills the instance defaults form the first time you set one up; listed below.

See [Managing holidays](#managing-holidays) for how to edit instance defaults and per-holiday overrides.

|Setting |Built-in fallback
|:----------|------------
| Default icon | `mdi:calendar-blank`
| Icon when a holiday is today | `mdi:calendar-star`
| Number of days to consider a holiday "soon" | 3
| Icon when a holiday is soon | `mdi:calendar`
| Date format (Python strftime syntax) | `%Y-%m-%d` (_see [http://strftime.org/](http://strftime.org/))_

## Translations

`strings.json` is the source of truth for the config/options flow text, and `translations/en.json` (English) is generated from it. The other language files under `custom_components/calendarific/translations/` are community-contributed and may lag behind or contain imperfect phrasing - corrections, updates, and additional languages are all welcome as pull requests.
