"""Small input-validation helpers shared across routes and agents."""

import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

# Free-mail domains — a contact on one of these is rarely a real decision maker.
GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "icloud.com", "proton.me", "protonmail.com",
}


def is_valid_email(email: str | None) -> bool:
    return bool(email) and bool(EMAIL_RE.match(email.strip()))


def is_business_email(email: str | None) -> bool:
    """True for a valid email that is not on a free-mail domain."""
    if not is_valid_email(email):
        return False
    return email.strip().rsplit("@", 1)[1].lower() not in GENERIC_EMAIL_DOMAINS


def is_valid_url(url: str | None) -> bool:
    return bool(url) and bool(URL_RE.match(url.strip()))


def normalise_url(url: str | None) -> str | None:
    """Add a scheme if missing and strip a trailing slash. None stays None."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def normalise_domain(url: str | None) -> str | None:
    """example.com from https://www.example.com/pricing?x=1"""
    normalised = normalise_url(url)
    if not normalised:
        return None
    host = normalised.split("://", 1)[1].split("/", 1)[0].split("?", 1)[0]
    return host[4:].lower() if host.lower().startswith("www.") else host.lower()


def sanitise_text(text: str | None, max_length: int = 20_000) -> str:
    """Collapse whitespace, drop control characters, and cap the length.

    Used on anything that came from a scrape, an upload, or a form before it
    reaches an LLM prompt or the database.
    """
    if not text:
        return ""
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()[:max_length]


def clamp_score(score: int | float | None) -> int | None:
    """Force a lead score into the 0–100 range. None stays None."""
    if score is None:
        return None
    return max(0, min(100, int(round(float(score)))))
