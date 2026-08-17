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
- `entry.options["defaults"]` – a single `{icon_normal, icon_today, icon_soon, days_as_soon, date_format, unit_of_measurement}` dict applied to every holiday in this instance unless overridden. Always fully populated (the config flow's `defaults` step and the options flow's `defaults` step both submit all six fields).
- `entry.options["holidays"]` – `{holiday_name: {...}}`, the set of holidays this instance tracks. Each value is a **sparse override dict** holding only the settings that differ from `entry.options["defaults"]` for that holiday — `{}` for a holiday with no customization. It can also hold a `name` key (a custom friendly name); `name` is per-holiday only, never part of `entry.options["defaults"]`, since a shared custom name across every holiday in an instance wouldn't make sense. `sensor.py`'s `async_setup_entry` resolves the effective per-holiday settings by merging `{**defaults, **override}` once, at entity-construction time (entities are always rebuilt on reload, so this doesn't need to be dynamic).
- Both are mutable via `CalendarificOptionsFlowHandler`, whose `async_step_init` is an action picker routing to: `async_step_holidays` (add/remove tracked holidays — removing one discards its override), `async_step_defaults` (edit the instance defaults), or `async_step_customize`/`async_step_customize_values` (pick one holiday, then set its override — submitting a value that matches the instance default is treated as "not overridden" and dropped from the override dict; a blank `name` is likewise treated as "not overridden" rather than compared against an instance default, since there isn't one; checking "reset to default" clears the override outright regardless of the other fields). Changing options triggers `async_update_options` → `hass.config_entries.async_reload(entry.entry_id)`.
- A custom `name` only changes the entity's displayed friendly name. It does **not** retroactively rename the entity's `entity_id` — HA assigns `entity_id` once, from the friendly name at first creation, and never auto-renames it afterward. This is standard HA behavior, not something specific to this integration.
- Every options-flow step that persists a change spreads the existing `config_entry.options` and overwrites only its own key (`{**self.config_entry.options, CONF_HOLIDAYS: holidays}`) — `async_create_entry` in an options flow *replaces* `options` wholesale rather than merging, so omitting this would silently wipe the other key.

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
