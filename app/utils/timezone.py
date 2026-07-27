from datetime import date, datetime
from zoneinfo import ZoneInfo

# Indian Standard Time (IST) ZoneInfo: GMT+05:30
IST = ZoneInfo("Asia/Kolkata")


def ist_now() -> datetime:
    """Returns the current naive datetime in Indian Standard Time (Asia/Kolkata, GMT+5:30)."""
    return datetime.now(IST).replace(tzinfo=None)


def ist_today() -> date:
    """Returns the current date in Indian Standard Time (Asia/Kolkata, GMT+5:30)."""
    return datetime.now(IST).date()


def format_ist(dt: datetime, fmt: str = "%b %d, %Y %I:%M %p") -> str:
    """Formats a datetime in Indian Standard Time."""
    if not dt:
        return "—"
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime("%b %d, %Y")
    if dt.tzinfo is None:
        # Treat naive datetime as IST if no timezone specified
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.strftime(fmt)
