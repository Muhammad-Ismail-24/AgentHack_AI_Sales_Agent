"""The booking link put in outreach emails and sent when a reply asks for a call."""

import re

from config.settings import settings
from utils.logger import logger


def generate_booking_link(lead_name: str) -> str:
    """Return the booking URL to offer this lead.

    CALENDAR_BOOKING_URL is a real, existing booking page (Cal.com, Calendly,
    Google Calendar appointment schedule — anything with a public URL) and is
    returned exactly as configured. Nothing is appended: Cal.com's `name`
    parameter prefills the *attendee's* name, so passing the company there put
    "Contact MIDTRANS | Official Logistics Channels" in the field meant for the
    prospect's own name and made them clear it before booking. Which company
    booked is already obvious from the email thread.

    The per-lead path this replaced is why it matters. It built
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
            return booking_url

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
