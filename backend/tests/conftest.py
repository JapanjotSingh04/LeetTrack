"""Shared test setup.

If mysql-connector-python is not installed (e.g. a minimal CI box) a tiny stub
is registered so the API can be imported. The real package is used when present.
"""
import sys
import types
from pathlib import Path

try:
    import mysql.connector  # noqa: F401
except ModuleNotFoundError:
    mysql_module = types.ModuleType("mysql")
    connector_module = types.ModuleType("mysql.connector")

    class _DriverError(Exception):
        pass

    class _IntegrityError(_DriverError):
        pass

    connector_module.Error = _DriverError
    connector_module.IntegrityError = _IntegrityError
    connector_module.connect = lambda **kwargs: None
    mysql_module.connector = connector_module
    sys.modules["mysql"] = mysql_module
    sys.modules["mysql.connector"] = connector_module

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
