"""Business-local clock helpers using the configured application timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import current_app, has_app_context


DEFAULT_TIMEZONE = "Asia/Aden"


def timezone_name():
    if has_app_context():
        return current_app.config.get("TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
    return DEFAULT_TIMEZONE


def business_now():
    """Return the current instant rendered in the configured business timezone."""
    try:
        zone = ZoneInfo(timezone_name())
    except Exception:
        zone = ZoneInfo(DEFAULT_TIMEZONE)
    return datetime.now(zone)


def business_today():
    """Return today's business date, not the operating system's local date."""
    return business_now().date()
