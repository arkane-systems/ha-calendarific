# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a Home Assistant custom integration (distributed via HACS) that creates sensor and calendar entities for public holidays via the [Calendarific API](https://calendarific.com/). It is a post-abandonment reboot of an integration originally by @pinkywafer. All code lives under `custom_components/calendarific/`.

**This repo has no live upstream.** The original integration (pinkywafer/Calendarific) appears abandoned by its developer, and this repo (cerebrate/Calendarific) is the maintained continuation. As a result, PRs are opened against **this repo's `master` branch only** — never against the upstream `pinkywafer/Calendarific` repo.

## Validation / commands

There is no local test suite and no lint/build step. Integration correctness is validated by Home Assistant's `hassfest` tool via GitHub Actions (`.github/workflows/hassfest.yaml`), which runs on every push and PR. To validate locally, use the official HA hassfest Docker image, or push to a branch and check the workflow result.

## Architecture

**YAML configuration is deprecated and unsupported.** The integration is config-entry-only (no `CONFIG_SCHEMA`/`PLATFORM_SCHEMA`, no `setup()`); any leftover `calendarific:` YAML block is simply ignored (with a warning) by HA's core config validation. All setup goes through the config flow.

### Instances

A config entry represents one **instance**: one `api_key` + `country` + `state` combination, tracking any number of holidays. Multiple instances can coexist side by side (e.g. one for US/US-KS, one for GB), each fully independent with its own API reader, device, and calendar. This is what makes multi-country/region setups and correct device grouping possible — grouping and scoping are keyed off `entry.entry_id`, not any shared global state.

### Data flow

```
__init__.py: async_setup_entry(entry)
  └─ creates one CalendarificApiReader (api.py) for this entry's api_key/country/state
       └─ fetches current-year AND next-year holidays from calendarific.com API
       └─ stores it at hass.data[DOMAIN][entry.entry_id]["apiReader"]
       └─ forwards to sensor.py AND calendar.py platforms for this entry
            ├─ sensor.py: one `calendarific` entity per holiday in entry.options["holidays"]
            └─ calendar.py: one `CalendarificCalendar` entity for this entry,
                             aggregating that entry's own sensor entities
```

### `hass.data[DOMAIN]` structure

Keyed by config entry, not flat domain-wide:

```python
hass.data[DOMAIN] = {
    entry.entry_id: {
        "apiReader": CalendarificApiReader,  # this instance's reader
        "sensor": {entity_id: calendarific}, # this instance's sensor entities
    },
    ...  # one such block per instance/config entry
}
```

### Config entry shape

- `entry.data` – connection-level, set once at creation: `api_key`, `country`, `state`.
- `entry.options["holidays"]` – a `{holiday_name: {icon_normal, icon_today, icon_soon, days_as_soon, date_format, unit_of_measurement}}` dict, the set of holidays this instance tracks. Set at creation via a `cv.multi_select` step in the config flow, and mutable afterward via `CalendarificOptionsFlowHandler` (add/remove holidays; per-holiday cosmetic settings currently aren't editable from the options UI — new selections get the defaults in `config_flow.py`'s `_default_holiday_config()`). Changing options triggers `async_update_options` → `hass.config_entries.async_reload(entry.entry_id)`.

### Device and calendar grouping

`device.py`'s `get_device_info(entry)` returns `identifiers={(DOMAIN, entry.entry_id)}` — every entity for an instance (however many holidays it holds) shares that one device, and separate instances never collide, since `entry.entry_id` is always unique. `CalendarificCalendar.unique_id` and the sensor `unique_id`s (`f"{entry.entry_id}_{slugify(holiday_name)}"`) are derived the same way, so the same holiday name in two different instances never collides either.

### Holiday date logic

`CalendarificApiReader` fetches both the **current year** and **next year** holiday lists. `get_date()` checks whether a holiday has already passed this year and, if so, returns next year's date. Sensor state is an integer (days remaining) or `"unknown"` when the holiday is not found in the API response.

### Sensor icon states

Icon switches based on the `days_as_soon` threshold:
- `> days_as_soon` days away → `icon_normal`
- `<= days_as_soon` days away → `icon_soon`
- today → `icon_today`

## Key conventions

- **Constants in `const.py`** – all domain-level constants, config keys, defaults, and platform names are defined here. Import from `const.py` rather than repeating string literals.
- **Version placeholders** – `VERSION` in `const.py` is a human-readable string and `"version"` in `manifest.json` is kept at `"0.0.0"` in the repo. Both are overwritten by the release CI workflow (`.github/workflows/main.yml`) using `sed` when a GitHub release is published. Do not manually bump `manifest.json` version.
- **Sensor state = days remaining** (integer `0` or positive). State is `"unknown"` only when the holiday name is not found in the API data.
- **`api.py`** holds the Calendarific API client: `calendarificAPI` (lowercase) is a thin HTTP wrapper around the Calendarific v2 REST API; `CalendarificApiReader` (PascalCase) is the per-instance cache/updater that wraps it; `fetch_holiday_names()` is a standalone helper used by the config/options flow to list available holidays for a country/state before an entry (and therefore a reader) exists. It's a separate module (not part of `__init__.py`) specifically so `config_flow.py` can import it without reaching into the integration's setup module.
- **Translations** – UI config/options flow strings live in `translations/<lang>.json`. `en.json` is the source of truth; other files are community-contributed and may lag behind new flow steps.
- **Entity `unique_id`** – every entity that exposes `device_info` (via `device.py`'s `get_device_info()`) must also expose a stable `unique_id`, per HA's requirement (enforced from 2027.8.0) that a device-linked entity have one. All of them are derived from `entry.entry_id`, so they stay unique and stable across restarts without needing to persist a random ID anywhere.
- **Old (pre-refactor) config entries are incompatible.** `async_setup_entry` raises `ConfigEntryError` if `entry.data` doesn't contain `api_key` (the old one-entry-per-holiday shape used a different key set entirely). There's no migration path — remove and re-add the integration.

## Release process

On GitHub release publish, the CI workflow (`.github/workflows/main.yml`):
1. Replaces `VERSION` in `const.py` and `"version"` in `manifest.json` with the tag name.
2. Zips `custom_components/calendarific/` as `calendarific.zip` and attaches it to the release (HACS downloads this zip).
