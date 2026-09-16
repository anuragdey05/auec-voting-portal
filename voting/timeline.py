"""
voting/timeline.py

Single source of truth for election timeline.

Reads ELECTION_START / ELECTION_END from environment (ISO format, IST assumed).
Falls back to VOTING_OPEN / VOTING_CLOSE for backward compatibility.

All comparisons use server-side UTC → IST conversion.
"""

import os
import pytz
from datetime import datetime
from django.utils import timezone

IST = pytz.timezone("Asia/Kolkata")

# Wide-open defaults for local development
_DEFAULT_START = "2024-01-01T00:00:00"
_DEFAULT_END = "2030-12-31T23:59:59"


def get_election_window():
    """
    Return (start_dt, end_dt) as timezone-aware IST datetimes.
    Reads ELECTION_START / ELECTION_END env vars (preferred),
    falling back to VOTING_OPEN / VOTING_CLOSE.
    """
    start_str = os.getenv("ELECTION_START") or os.getenv("VOTING_OPEN", _DEFAULT_START)
    end_str = os.getenv("ELECTION_END") or os.getenv("VOTING_CLOSE", _DEFAULT_END)

    start_dt = IST.localize(datetime.fromisoformat(start_str))
    end_dt = IST.localize(datetime.fromisoformat(end_str))
    return start_dt, end_dt


def get_election_status():
    """
    Return a dict describing the current election state.

    {
        "status": "upcoming" | "active" | "ended",
        "server_now": "ISO string (UTC)",
        "start": "ISO string (UTC)",
        "end": "ISO string (UTC)",
        "start_ist": "human-readable IST string",
        "end_ist": "human-readable IST string",
    }
    """
    start_dt, end_dt = get_election_window()
    now = timezone.now()
    now_ist = now.astimezone(IST)

    if now_ist < start_dt:
        status = "upcoming"
    elif now_ist >= end_dt:
        status = "ended"
    else:
        status = "active"

    return {
        "status": status,
        "server_now": now.isoformat(),
        "start": start_dt.astimezone(pytz.UTC).isoformat(),
        "end": end_dt.astimezone(pytz.UTC).isoformat(),
        "start_ist": start_dt.strftime("%-d %B %Y at %-I:%M %p IST"),
        "end_ist": end_dt.strftime("%-d %B %Y at %-I:%M %p IST"),
    }


def require_active_election():
    """
    Raise VoteError if the election is not currently active.
    Import VoteError here to avoid circular imports.
    """
    from .services import VoteError

    start_dt, end_dt = get_election_window()
    now_ist = timezone.now().astimezone(IST)

    if now_ist < start_dt:
        opens_str = start_dt.strftime("%-d %B %Y at %-I:%M %p IST")
        raise VoteError(f"Sorry, voting begins on {opens_str}.")
    if now_ist >= end_dt:
        raise VoteError("Sorry, voting has ended.")
