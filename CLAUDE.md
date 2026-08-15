# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This is a Home Assistant custom integration (distributed via HACS) that creates sensor and calendar entities for public holidays via the [Calendarific API](https://calendarific.com/). It is a post-abandonment reboot of an integration originally by @pinkywafer. All code lives under `custom_components/calendarific/`.

**This repo has no live upstream.** The original integration (pinkywafer/Calendarific) appears abandoned by its developer, and this repo (cerebrate/Calendarific) is the maintained continuation. As a result, PRs are opened against **this repo's `master` branch only** — never against the upstream `pinkywafer/Calendarific` repo.

## Validation / commands

There is no local test suite and no lint/build step. Integration correctness is validated by Home Assistant's `hassfest` tool via GitHub Actions (`.github/workflows/hassfest.yaml`), which runs on every push and PR. To validate locally, use the official HA hassfest Docker image, or push to a branch and check the workflow result.

## Architecture

### Data flow

```
__init__.py (CalendarificApiReader)
  └─ fetches current-year AND next-year holidays from calendarific.com API
       └─ sensor.py (calendarific entity, one per holiday)
            └─ calendar.py (CalendarificCalendar + EntitiesCalendarData)
```

### Setup paths

There are **two parallel setup paths**:

1. **YAML** – `setup()` in `__init__.py` handles the integration-level config (API key, country, state). This creates the `CalendarificApiReader` and stores it in `hass.data[DOMAIN]["apiReader"]`.
2. **UI / config flow** – `async_setup_entry()` in `__init__.py` + `config_flow.py` handles per-sensor config (holiday name, icons, date format, etc.). `CalendarificConfigFlow.__init__` reads `hass.data[DOMAIN]["apiReader"]`, so the YAML setup (or a prior YAML-equivalent) **must** have run first.

### `hass.data[DOMAIN]` structure

```python
hass.data[DOMAIN] = {
    "apiReader": CalendarificApiReader,  # set by integration setup
    "sensor": {entity_id: calendarific}, # populated as sensors are added
    "calendar": EntitiesCalendarData,    # created lazily by first sensor
}
```

### Calendar lazy-loading

`CalendarificCalendar` (the HA calendar entity) is **not** set up during integration init. It is created inside `sensor.async_added_to_hass()` when the first sensor is registered, using `async_load_platform`. `CalendarificCalendar.instances` (a class variable) prevents duplicate instances.

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
- **`calendarificAPI`** (lowercase) is a thin HTTP wrapper around the Calendarific v2 REST API. `CalendarificApiReader` (PascalCase) is the HA-layer cache/updater that wraps it.
- **Translations** – UI config flow strings live in `translations/<lang>.json`. `en.json` is the source of truth; other files are community-contributed translations.

## Release process

On GitHub release publish, the CI workflow (`.github/workflows/main.yml`):
1. Replaces `VERSION` in `const.py` and `"version"` in `manifest.json` with the tag name.
2. Zips `custom_components/calendarific/` as `calendarific.zip` and attaches it to the release (HACS downloads this zip).
