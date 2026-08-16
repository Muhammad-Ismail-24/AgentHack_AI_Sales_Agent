"""The booking link put in outreach emails and sent when a reply asks for a call."""

import re
from urllib.parse import quote

from config.settings import settings
from utils.logger import logger


def generate_booking_link(lead_name: str) -> str:
    """Return the booking URL to offer this lead.

    CALENDAR_BOOKING_URL is a real, existing booking page (Cal.com, Calendly,
    Google Calendar appointment schedule — anything with a public URL) and is
    returned as-is, with the company name attached as a query parameter so the
    booking form can prefill and the sales rep knows who booked. Query params
    are safe: a scheduler that does not recognise one ignores it, whereas the
    path must match a real event.

    That last point is why the old behaviour is gone. It built
    "{CALENDAR_BASE_URL}/{slugified-company}", inventing a distinct path per
    lead — cal.com/admin/contact-midtrans-official-logistics-channels — and no
    such event type exists, so every link in every email 404'd. A booking link
    is the call to action of the whole email; a broken one wastes the outreach.

    Falls back to the old slug shape only when CALENDAR_BOOKING_URL is unset,
    and says so, since there is nothing better to offer at that point.
    """
    try:
        booking_url = (settings.CALENDAR_BOOKING_URL or "").strip()
        if booking_url:
            company = (lead_name or "").strip()
            if not company:
                return booking_url
            separator = "&" if "?" in booking_url else "?"
            return f"{booking_url}{separator}name={quote(company)}"

        logger.warning(
            "CALENDAR_BOOKING_URL is not set — falling back to a generated "
            "%s/<company> link, which 404s unless that event type exists. "
            "Set it to your real booking page.",
            settings.CALENDAR_BASE_URL,
        )
        slug = re.sub(r"[^a-z0-9]+", "-", (lead_name or "").strip().lower()).strip("-")
        return f"{settings.CALENDAR_BASE_URL}/{slug or 'lead'}"
    except Exception as e:
        logger.error(f"Error generating booking link for '{lead_name}': {e}")
        return (settings.CALENDAR_BOOKING_URL or f"{settings.CALENDAR_BASE_URL}/lead")
