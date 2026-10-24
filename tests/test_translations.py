"""Checks that keep strings.json, translations/en.json and the code in step."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import homeassistant
import pytest

from custom_components.calendarific.helpers import default_title, instance_unique_id

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "calendarific"
CORE_STRINGS = Path(homeassistant.__file__).resolve().parent / "strings.json"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _resolve(value: Any, core: dict[str, Any]) -> Any:
    """Replace [%key:common::...%] references with Home Assistant's own text."""
    if isinstance(value, dict):
        return {key: _resolve(item, core) for key, item in value.items()}
    match = re.fullmatch(r"\[%key:([^%]+)%\]", value)
    if match is None:
        return value
    node: Any = core
    for part in match.group(1).split("::"):
        node = node[part]
    assert isinstance(node, str)
    return node


STRINGS = _load(INTEGRATION / "strings.json")
EN = _load(INTEGRATION / "translations" / "en.json")


def test_en_json_is_strings_json_with_common_keys_resolved() -> None:
    assert EN == _resolve(STRINGS, _load(CORE_STRINGS))


def _steps() -> list[tuple[str, dict[str, Any]]]:
    return [
        (f"{section}.{name}", step)
        for section in ("config", "options")
        for name, step in STRINGS[section]["step"].items()
    ]


@pytest.mark.parametrize(("name", "step"), _steps(), ids=[name for name, _ in _steps()])
def test_every_form_field_is_described(name: str, step: dict[str, Any]) -> None:
    if "data" not in step:
        return  # a menu or other field-less step
    assert set(step["data"]) == set(step["data_description"]), name


def test_every_translation_key_the_code_uses_exists() -> None:
    assert set(re.findall(r'translation_key="(\w+)"', _all_source())) <= set(STRINGS["exceptions"])

    config = STRINGS["config"]
    options = STRINGS["options"]
    assert {
        "no_holidays_found",
        "no_holidays_selected",
        "invalid_auth",
        "cannot_connect",
        "rate_limited",
        "already_configured",
    } <= set(config["error"])
    assert {"already_configured", "reauth_successful", "reconfigure_successful"} <= set(
        config["abort"]
    )
    assert {"no_holidays_configured", "invalid_auth", "cannot_connect", "rate_limited"} <= set(
        options["abort"]
    )
    assert set(options["step"]["init"]["menu_options"]) == {"holidays", "defaults", "customize"}


def test_every_entity_translation_key_has_a_name_and_an_icon() -> None:
    used = set(re.findall(r'_attr_translation_key = "(\w+)"', _all_source()))
    assert used == {"next_holiday", "holidays"}

    icons = _load(INTEGRATION / "icons.json")["entity"]
    for platform, keys in (("sensor", {"next_holiday"}), ("calendar", {"holidays"})):
        assert keys <= set(STRINGS["entity"][platform]), platform
        assert keys <= set(icons[platform]), platform
        for key in keys:
            assert icons[platform][key]["default"].startswith("mdi:")


def _all_source() -> str:
    return "".join(path.read_text(encoding="utf-8") for path in INTEGRATION.glob("*.py"))


def test_default_title() -> None:
    assert default_title("us", "ks") == "Calendarific (US - KS)"
    assert default_title("gb", "") == "Calendarific (GB)"


def test_instance_unique_id() -> None:
    assert instance_unique_id("US", "KS") == "us-ks"
    assert instance_unique_id(" gb ", "  ") == "gb"
