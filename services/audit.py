"""Audit logging system for tracking all library operations with full detail."""

import json
import logging
import os
from datetime import datetime
from config import AUDIT_ENABLED

AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audit.log")
logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    """Check if audit logging is currently enabled."""
    from config import AUDIT_ENABLED
    return AUDIT_ENABLED


def toggle(enabled: bool) -> bool:
    """Toggle audit mode and log to standard app.log."""
    from config import AUDIT_ENABLED
    global AUDIT_ENABLED

    old_value = AUDIT_ENABLED

    # Update runtime value
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
