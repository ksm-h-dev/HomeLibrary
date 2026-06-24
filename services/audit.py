"""Audit logging system for tracking all library operations with full detail."""

import json
import logging
import os
from datetime import datetime
from config import AUDIT_ENABLED

AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.log")
_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")
logger = logging.getLogger(__name__)


def _read_settings():
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _write_settings(data: dict):
    try:
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error("Failed to write settings: %s", e)


def is_enabled() -> bool:
    """Check if audit logging is currently enabled.
    Checks settings.json first, then falls back to config.py.
    """
    settings = _read_settings()
    if "audit_enabled" in settings:
        return settings["audit_enabled"]
    return AUDIT_ENABLED


def toggle(enabled: bool) -> bool:
    """Toggle audit mode. Persists to settings.json, no config.py rewrite."""
    old_value = is_enabled()

    # Persist to settings.json
    settings = _read_settings()
    settings["audit_enabled"] = enabled
    _write_settings(settings)

    # Update runtime value for immediate effect
    import config as config_module
    config_module.AUDIT_ENABLED = enabled

    if enabled and not old_value:
        logger.warning("AUDIT MODE ENABLED — Detailed action logging activated (audit.log)")
    elif not enabled and old_value:
        logger.warning("AUDIT MODE DISABLED — Detailed action logging deactivated")

    return enabled


def log_audit(event_type: str, details: dict, source: str = "system"):
    """Write an audit entry to audit.log and app.log.

    Args:
        event_type: Event category (source_scan_start, book_updated, etc.)
        details: Dict with full event details (file names, counts, errors, etc.)
        source: Origin of the event ("api", "importer", "setup", "ui")
    """
    if not is_enabled():
        return

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "source": source,
        **details
    }

    # Also write to app.log for visibility
    logger.info("AUDIT: %s | %s", event_type, json.dumps(details, ensure_ascii=False, default=str))

    # Write to dedicated audit log
    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.error("Failed to write audit log: %s", e)
