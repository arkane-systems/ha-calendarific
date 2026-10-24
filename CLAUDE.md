# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a Home Assistant custom integration (distributed via HACS) that creates sensor and calendar entities for public holidays via the [Calendarific API](https://calendarific.com/). It is a post-abandonment reboot of an integration originally by @pinkywafer. All code lives under `custom_components/calendarific/`.

**This repo has no live upstream.** The original integration (pinkywafer/Calendarific) appears abandoned by its developer, and this repo (arkane-systems/ha-calendarific) is the maintained continuation. As a result, PRs are opened against **this repo's `master` branch only** — never against the upstream `pinkywafer/Calendarific` repo.

## Validation / commands

There is no build step. Integration correctness is validated by Home Assistant's `hassfest` tool via GitHub Actions (`.github/workflows/hassfest.yaml`) and by the pytest suite (`.github/workflows/tests.yaml`), both on every push and PR. To run hassfest locally, use the official HA hassfest Docker image, or push to a branch and check the workflow result.

```sh
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest --cov=custom_components.calendarific --cov-report=term-missing
```

Tests use `pytest-homeassistant-custom-component` to run a real in-memory Home Assistant. `tests/conftest.py` provides `fake_api` (replaces the HTTP layer with canned holiday data and records calls) and `frozen_today` (freezes time at 2026-10-24); `tests/common.py` has the entry/sensor helpers. Always look entities up by unique ID suffix (`entity_id_for`, `sensor_id`) rather than hard-coding entity IDs.

Progress towards the Platinum tier of the HA integration quality scale (a self-imposed yardstick; HA doesn't grade custom integrations) is tracked per rule in `custom_components/calendarific/quality_scale.yaml`. Keep it current when behavior changes.

## Architecture

**YAML configuration is deprecated and unsupported.** The integration is config-entry-only (no `CONFIG_SCHEMA`/`PLATFORM_SCHEMA`, no `setup()`); any leftover `calendarific:` YAML block is simply ignored (with a warning) by HA's core config validation. All setup goes through the config flow.

### Instances

A config entry represents one **instance**: one `api_key` + `country` + `state` combination, tracking any number of holidays. Multiple instances can coexist side by side (e.g. one for US/US-KS, one for GB), each fully independent with its own coordinator, device, and calendar. This is what makes multi-country/region setups and correct device grouping possible — grouping and scoping are keyed off `entry.entry_id`, not any shared global state.

### Data flow

```
__init__.py: async_setup_entry(entry)
  └─ creates one CalendarificCoordinator (coordinator.py) for this entry's api_key/country/state
       └─ first refresh fetches current-year AND next-year holidays via CalendarificClient (api.py),
          using HA's shared aiohttp session; stored as entry.runtime_data
       └─ forwards to sensor.py AND calendar.py platforms for this entry
            ├─ sensor.py: one HolidaySensor per holiday in entry.options["holidays"], plus one NextHolidaySensor
            └─ calendar.py: one CalendarificCalendar for this entry
```

Entities (all `CalendarificEntity` subclasses, entity.py) never fetch anything: they derive their state from `coordinator.data` (a `HolidayData` snapshot) and today's date each time HA writes their state.

### Coordinator behavior

- `entry.runtime_data` is the `CalendarificCoordinator`; `CalendarificConfigEntry` (coordinator.py) is the typed alias. There is no `hass.data[DOMAIN]`.
- It refetches once a day (`REFRESH_INTERVAL`). The coordinator, not the entities, owns a local-midnight timer that calls `async_update_listeners()` so day counts roll over with no API call, and also requests a refresh when the year changes (the cache holds today's year and the next).
- **Outages:** a failed refresh keeps serving the cached data for as long as it still covers today's year (the cache holds two years), logging one warning and one recovery message, and retries every `RETRY_INTERVAL`. Failed requests count against Calendarific's monthly quota (500 on the free plan), so the retry is deliberately slow and a failed first-year request skips the second. When the cache no longer covers today, `UpdateFailed` makes the entities unavailable.
- `CalendarificAuthError` (HTTP 401/403) raises `ConfigEntryAuthFailed`, which starts the reauth flow in `config_flow.py`. Other API errors during first setup raise `ConfigEntryNotReady`.

### Config entry shape

- `entry.data` – connection-level: `api_key`, `country`, `state`. Changed only by the reauth and reconfigure flows.
- `entry.unique_id` – `helpers.instance_unique_id(country, state)` (lower-case, e.g. `us-ks`), so each place can be added once. The config entry schema is version 1, minor 3 (`CONFIG_ENTRY_*` in `const.py`); `async_migrate_entry` in `__init__.py` gave older entries their ID (leaving a pre-existing duplicate without one rather than refusing to load it) and stripped the removed `unit_of_measurement` key from `defaults` and every holiday override.
- `entry.options["defaults"]` – a single `{icon_normal, icon_today, icon_soon, days_as_soon, date_format}` dict applied to every holiday in this instance unless overridden. Always fully populated (the config flow's `defaults` step and the options flow's `defaults` step both submit all five fields). The unit is not configurable: holiday sensors are `SensorDeviceClass.DURATION` in `UnitOfTime.DAYS`.
- `entry.options["holidays"]` – `{holiday_name: {...}}`, the set of holidays this instance tracks. Each value is a **sparse override dict** holding only the settings that differ from `entry.options["defaults"]` for that holiday — `{}` for a holiday with no customization. It can also hold a `name` key (a custom friendly name); `name` is per-holiday only, never part of `entry.options["defaults"]`, since a shared custom name across every holiday in an instance wouldn't make sense. `sensor.py`'s `async_setup_entry` resolves the effective per-holiday settings by merging `{**defaults, **override}` once, at entity-construction time (entities are always rebuilt on reload, so this doesn't need to be dynamic).
- Both are mutable via `CalendarificOptionsFlowHandler`, whose `async_step_init` is an action picker routing to: `async_step_holidays` (add/remove tracked holidays — removing one discards its override), `async_step_defaults` (edit the instance defaults), or `async_step_customize`/`async_step_customize_values` (pick one holiday, then set its override — submitting a value that matches the instance default is treated as "not overridden" and dropped from the override dict; a blank `name` is likewise treated as "not overridden" rather than compared against an instance default, since there isn't one; checking "reset to default" clears the override outright regardless of the other fields). `CalendarificOptionsFlowHandler` is an `OptionsFlowWithReload`, so saving options reloads the entry; HA forbids registering an update listener alongside it, so renaming an instance does not reload it (the device and calendar names are only read when entities are created).
- A custom `name` only changes the entity's displayed friendly name. It does **not** retroactively rename the entity's `entity_id` — HA assigns `entity_id` once, from the friendly name at first creation, and never auto-renames it afterward. This is standard HA behavior, not something specific to this integration.
- Every options-flow step that persists a change spreads the existing `config_entry.options` and overwrites only its own key (`{**self.config_entry.options, CONF_HOLIDAYS: holidays}`) — `async_create_entry` in an options flow *replaces* `options` wholesale rather than merging, so omitting this would silently wipe the other key.

### Config flow

- **Setup:** `user` (key, country, state) → `defaults` → `holidays`. The unique ID is set and checked first, so a duplicate is rejected before any API request is spent. Errors are classified by `_error_key`: `invalid_auth`, `rate_limited`, `cannot_connect`, plus `no_holidays_found`.
- **Reauth:** started by `ConfigEntryAuthFailed`; asks for a new key and verifies it before saving.
- **Reconfigure:** `reconfigure` edits key, country and state. If the place is unchanged it just updates the entry; otherwise `reconfigure_holidays` re-picks holidays (those still on offer pre-selected, their overrides kept), the unique ID updates, and the title follows the place only if it was still the generated default. It does its own conflict check against other entries because `_abort_if_unique_id_configured` would match the entry being reconfigured. Dropped holidays' entities are removed by the stale-entity sweep at the next setup.
- **Options:** a translated menu (`init`) leading to `holidays`, `defaults` and `customize`/`customize_values`.

### Entity naming

- **Holiday sensors** have `has_entity_name = False` and are named after the holiday itself (or its custom name), so they read as "Christmas Day". This is the deliberate `has-entity-name` exemption in `quality_scale.yaml`: prefixing the instance title would give "Calendarific (US - KS) Christmas Day" and long entity IDs.
- **Next Holiday and the calendar** have `has_entity_name = True`. Next Holiday uses `translation_key = "next_holiday"`, giving "<instance> Next holiday", which tells several instances apart; the calendar has `name = None`, so it takes the device's name. Entity names only translate when `has_entity_name` is True, which is why the holiday sensors can't.
- `icons.json` covers those two fixed entities. Holiday sensors keep the user-configurable `icon` property (the three icon settings are deliberate).

### Repairs, stale entities and diagnostics

- **Stale entities:** `__init__._async_remove_stale_entities` runs on every setup and deletes registry entries whose unique ID is not one of this instance's expected IDs (`helpers.holiday_unique_id` and friends), so deselecting a holiday removes its sensor.
- **Repair issue `holiday_missing`:** after every successful fetch the coordinator calls `issues.async_sync_missing_holiday_issues`, which raises one fixable issue per tracked holiday that no fetched year lists (`HolidayData.knows`) and clears resolved ones. A holiday that is listed but has no upcoming date is *not* an issue. Outages neither raise nor clear issues. `repairs.py` provides the fix flow (stop tracking the holiday and reload); `async_remove_entry` clears an instance's issues.
- **Diagnostics:** `diagnostics.py` redacts the API key and reports the entry, coordinator state, cache size per year and each tracked holiday's next date. Country and state are deliberately not redacted.

### Device and calendar grouping

`device.py`'s `get_device_info(entry)` returns `identifiers={(DOMAIN, entry.entry_id)}` — every entity for an instance (however many holidays it holds) shares that one device, and separate instances never collide, since `entry.entry_id` is always unique. `CalendarificCalendar.unique_id` and the sensor `unique_id`s (`f"{entry.entry_id}_{slugify(holiday_name)}"`) are derived the same way, so the same holiday name in two different instances never collides either.

### Holiday date logic

`HolidayData` (api.py) is an immutable snapshot of the holidays for the fetched years, indexed by name (the first of any duplicate names in a year wins). `next_occurrence(name, today)` returns the first occurrence on or after today, looking through this year's list and then next year's, so a holiday that has passed rolls over to next year's date and one that exists only next year is still found. `next_holiday()` picks the soonest of several (ties break on name) and `occurrences()` serves the calendar's date ranges. A holiday that isn't found gives a sensor state of `None` (shown as unknown).

"Today" is always passed in rather than read from the system clock. `api.py` has no `homeassistant` dependency by design (see below), so it can't call `homeassistant.util.dt` itself; `CalendarificEntity._today()` and the coordinator use `dt_util.now().date()`. Do not let `api.py` fall back to the bare system clock — the host's OS timezone (frequently UTC in containers/HAOS) is not necessarily HA's *configured* timezone, and comparing against it rolls "today" over at the wrong wall-clock time relative to the user's local midnight.

### Sensor icon states

Icon switches based on the `days_as_soon` threshold:
- `> days_as_soon` days away → `icon_normal`
- `<= days_as_soon` days away → `icon_soon`
- today → `icon_today`

## Key conventions

- **Constants in `const.py`** – all domain-level constants, config keys, defaults, and platform names are defined here. Import from `const.py` rather than repeating string literals.
- **Version bumps are manual.** `VERSION` in `const.py` and `"version"` in `manifest.json` must be bumped together, by hand, as part of the commit that's tagged for release — there is no CI step that stamps them. HACS installs directly from the tagged repository tree, so whatever these two fields say at that commit is what ships.
- **Sensor state = days remaining** (integer `0` or positive). State is `None` (shown as unknown) only when the holiday name is not found in the API data.
- **`api.py`** holds the Calendarific API client and has no `homeassistant` dependency: `CalendarificClient` is an async wrapper around the v2 holidays endpoint that takes an `aiohttp.ClientSession` from its caller (so HA's shared session is injected), applies a request timeout, and turns failures into `CalendarificAuthError` / `CalendarificRateLimitError` / `CalendarificConnectionError`. It never puts `str(err)` of an aiohttp error in a message, because those can embed the request URL and so the API key. `Holiday` and `HolidayData` are the data model. It's a separate module (not part of `__init__.py`) so `config_flow.py` can import it without reaching into the integration's setup module.
- **Translations** – `strings.json` is the source of truth; `translations/en.json` is a copy with the `[%key:common::...%]` references resolved to Home Assistant's own text, and `tests/test_translations.py` fails if they drift or if a form field lacks a `data_description`. Add any new string to both. HA strips a trailing period from `exceptions` messages, so omit it there. The other language files are community-contributed and may lag behind new flow steps; HA falls back to English for missing keys.
- **Entity `unique_id`** – every entity that exposes `device_info` (via `device.py`'s `get_device_info()`) must also expose a stable `unique_id`, per HA's requirement (enforced from 2027.8.0) that a device-linked entity have one. All of them are derived from `entry.entry_id`, so they stay unique and stable across restarts without needing to persist a random ID anywhere.
- **Old (pre-refactor) config entries are incompatible.** `async_setup_entry` raises a translated `ConfigEntryError` (`legacy_entry`) if `entry.data` doesn't contain `api_key` (the old one-entry-per-holiday shape used a different key set entirely). There's no migration path — remove and re-add the integration.

## Release process

There is no release-time build step. HACS installs this integration by pulling `custom_components/calendarific/` directly from the tagged commit (`hacs.json` has no `zip_release`), so before tagging a release, bump `VERSION` in `const.py` and `"version"` in `manifest.json` by hand to match the release tag and commit that.
