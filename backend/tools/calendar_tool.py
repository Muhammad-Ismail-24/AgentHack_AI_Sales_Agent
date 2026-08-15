"""Cal.com-style booking link generator used by combined_processing_agent."""

import re

from config.settings import settings
from utils.logger import logger


def generate_booking_link(lead_name: str) -> str:
    """Return a Cal.com style booking URL for the given lead/company name.

    slug = lead_name lowercased, non-alphanumerics replaced with hyphens.
    Later: integrate the real Cal.com API if time allows.
    """
    try:
        slug = lead_name.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
        if not slug:
            slug = "lead"
        return f"{settings.CALENDAR_BASE_URL}/{slug}"
    except Exception as e:
        logger.error(f"Error generating booking link for '{lead_name}': {e}")
        return f"{settings.CALENDAR_BASE_URL}/lead"
