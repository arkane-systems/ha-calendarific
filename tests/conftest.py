"""Test setup.

api.py has no relative imports and no homeassistant dependency, so it can be
loaded as a standalone module without needing homeassistant installed or
custom_components/calendarific/__init__.py (which does import homeassistant)
to run. sensor.py and config_flow.py don't have this property - they use
relative imports and import homeassistant directly - so they aren't covered
here; testing them would need the full pytest-homeassistant-custom-component
harness instead.

api.py is loaded directly by file path via importlib rather than added to
sys.path, since custom_components/calendarific/ also contains a calendar.py -
putting that directory on sys.path would shadow the stdlib calendar module
(which requests imports transitively via http.cookiejar) with it.
"""
import importlib.util
import sys
from pathlib import Path

_API_PATH = Path(__file__).resolve().parent.parent / "custom_components" / "calendarific" / "api.py"
_spec = importlib.util.spec_from_file_location("api", _API_PATH)
_api = importlib.util.module_from_spec(_spec)
sys.modules["api"] = _api
_spec.loader.exec_module(_api)
