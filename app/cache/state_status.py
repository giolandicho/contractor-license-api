"""
Thread-safe in-memory tracker for per-state scraper success/failure.
Used by /status to surface operational health without hitting government sites.
"""
import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_state = {}  # { "CA": {"last_success": datetime|None, "last_failure": datetime|None} }

TRACKED_STATES = ["CA", "TX", "FL"]
OPERATIONAL_WINDOW_SECONDS = 3600  # 60 minutes


def _ensure(state):
    if state not in _state:
        _state[state] = {"last_success": None, "last_failure": None}


def record_success(state):
    with _lock:
        _ensure(state)
        _state[state]["last_success"] = datetime.now(tz=timezone.utc)


def record_failure(state):
    with _lock:
        _ensure(state)
        _state[state]["last_failure"] = datetime.now(tz=timezone.utc)


def get_all():
    now = datetime.now(tz=timezone.utc)
    result = {}
    with _lock:
        for state in TRACKED_STATES:
            entry = _state.get(state, {})
            last_success = entry.get("last_success")
            last_failure = entry.get("last_failure")
            if last_success is None:
                status = "unknown"
            elif (now - last_success).total_seconds() <= OPERATIONAL_WINDOW_SECONDS:
                status = "operational"
            else:
                status = "degraded"
            result[state] = {
                "status": status,
                "last_success": last_success.isoformat() if last_success else None,
                "last_failure": last_failure.isoformat() if last_failure else None,
            }
    return result
