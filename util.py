"""Small shared helpers used by every source scraper."""
import datetime
import hashlib
import re

_DATE_FORMATS = (
    "%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%Y/%m/%d",
    "%B %d, %Y", "%b %d, %Y", "%d %B %Y",
)


def to_iso(value):
    """Best-effort conversion of a messy date string to YYYY-MM-DD.

    Returns None when the value isn't a real date (e.g. "Open until filled").
    """
    if not value:
        return None
    s = str(value).strip()
    # Pull a date-looking token out of a longer string if present.
    m = re.search(r"\d{1,4}[/-]\d{1,2}[/-]\d{1,4}", s)
    token = m.group(0) if m else s
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(token, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "")).date().isoformat()
    except (ValueError, AttributeError):
        return None


def clean(text):
    """Collapse whitespace and strip."""
    if text is None:
        return None
    return re.sub(r"\s+", " ", str(text)).strip() or None


def make_id(source_key, *parts):
    """Stable short id so the same posting keeps the same id across runs."""
    raw = "|".join(p for p in parts if p)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{source_key}-{digest}"
