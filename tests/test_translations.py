"""Checks that keep strings.json, translations/en.json and the code in step."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

from custom_components.calendarific.helpers import default_title, instance_unique_id

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "calendarific"


def _load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


STRINGS = _load(INTEGRATION / "strings.json")
EN = _load(INTEGRATION / "translations" / "en.json")


def _mismatches(source: Any, translated: Any, path: str = "") -> list[str]:
    """Compare strings.json with en.json.

    Literal strings must match exactly. A [%key:common::...%] reference only
    needs a non-empty string in en.json: Home Assistant rewords its common
    strings between releases (for example "Re-configuration" became
    "Reconfiguration"), so the exact text is not ours to pin.
    """
    if isinstance(source, dict):
        if not isinstance(translated, dict) or set(source) != set(translated):
            return [path or "<root>"]
        return [
            problem
            for key in source
            for problem in _mismatches(source[key], translated[key], f"{path}.{key}".lstrip("."))
        ]
    if re.fullmatch(r"\[%key:[^%]+%\]", source):
        return [] if isinstance(translated, str) and translated else [path]
    return [] if source == translated else [path]


def test_en_json_is_strings_json_with_common_keys_resolved() -> None:
    assert _mismatches(STRINGS, EN) == []


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


LANGUAGE_FILES = sorted((INTEGRATION / "translations").glob("*.json"))
OTHER_LANGUAGES = [path for path in LANGUAGE_FILES if path.stem != "en"]
EN_FLAT = _flatten(EN)


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


@pytest.mark.parametrize("path", OTHER_LANGUAGES, ids=[p.stem for p in OTHER_LANGUAGES])
class TestTranslationFiles:
    """Each language file must mirror English: nothing obsolete, nothing missing."""

    def test_has_no_obsolete_keys(self, path: Path) -> None:
        assert sorted(set(_flatten(_load(path))) - set(EN_FLAT)) == []

    def test_has_every_string(self, path: Path) -> None:
        assert sorted(set(EN_FLAT) - set(_flatten(_load(path)))) == []

    def test_keeps_the_same_placeholders(self, path: Path) -> None:
        for key, text in _flatten(_load(path)).items():
            assert _placeholders(text) == _placeholders(EN_FLAT[key]), key

    def test_is_valid_message_format(self, path: Path) -> None:
        """An apostrophe next to a brace starts ICU quoting and swallows the placeholder."""
        for key, text in _flatten(_load(path)).items():
            assert "{{" not in text and "}}" not in text, key
            assert not re.search(r"'\{|\}'", text), key

    def test_description_quotes_the_reset_checkbox_label(self, path: Path) -> None:
        flat = _flatten(_load(path))
        label = flat["options.step.customize_values.data.reset_to_default"]
        assert f"'{label}'" in flat["options.step.customize_values.description"]


def test_english_description_quotes_the_reset_checkbox_label() -> None:
    label = EN_FLAT["options.step.customize_values.data.reset_to_default"]
    assert f"'{label}'" in EN_FLAT["options.step.customize_values.description"]


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
