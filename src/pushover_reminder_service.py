import datetime
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import time

import requests


try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # dotenv is optional; env vars can be provided by the shell
    pass


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_DIR = PROJECT_ROOT / "db"
CALENDAR_FILE = DB_DIR / "calendar.json"
REMINDERS_FILE = DB_DIR / "pushover_reminders.json"


def _load_calendar_events() -> Dict[str, Any]:
    if not CALENDAR_FILE.exists():
        return {}
    try:
        return __import__("json").load(open(CALENDAR_FILE, "r"))
    except Exception:
        return {}


def _load_reminder_log() -> Dict[str, Any]:
    if not REMINDERS_FILE.exists():
        return {}
    try:
        return __import__("json").load(open(REMINDERS_FILE, "r"))
    except Exception:
        return {}


def _save_reminder_log(log: Dict[str, Any]) -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    import json

    with open(REMINDERS_FILE, "w") as f:
        json.dump(log, f, indent=2)
        f.flush()


def _parse_event_start_datetime(
    date_str: str, event_time: str, now: Optional[datetime.datetime] = None
) -> Optional[datetime.datetime]:
    """
    Parse the START time from the stored `event_time` string.

    Examples we handle:
    - "9:30-10;30" -> 09:30
    - "9:00 am -9:15" -> 09:00
    """
    try:
        event_date = datetime.date.fromisoformat(date_str)
    except Exception:
        return None

    if not isinstance(event_time, str) or not event_time.strip():
        return None

    s = event_time.strip().lower()

    # Find the first occurrence of H:MM with optional am/pm.
    # Supports forms like "1:41PM" and also "1: 52pm" (optional whitespace after colon).
    m = re.search(
        r"(\d{1,2})\s*:\s*(\d{2})\s*(am|pm)?",
        s,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3)

    try:
        if ampm:
            # Parse as 12-hour time with am/pm
            dt_time = datetime.datetime.strptime(
                f"{hour}:{minute:02d}{ampm.upper()}",
                "%I:%M%p",
            ).time()
            return datetime.datetime.combine(event_date, dt_time)

        # No am/pm:
        # - If hour looks like 24h (>= 13), treat as 24-hour.
        # - If hour is 1..12, pick AM/PM based on which start time is in the future
        #   relative to `now` (if provided). This makes "1:43" work like "1:43pm"
        #   when you're running in the afternoon.
        if hour >= 13:
            dt_time = datetime.time(hour=hour, minute=minute)
            return datetime.datetime.combine(event_date, dt_time)

        # hour is 1..12 (or 0..12); interpret as 12-hour
        h12 = hour % 12  # 12 -> 0 for conversion to 12-hour clock
        dt_am = datetime.datetime.combine(event_date, datetime.time(hour=h12, minute=minute))
        dt_pm = datetime.datetime.combine(event_date, datetime.time(hour=h12 + 12, minute=minute))

        if now is not None:
            if dt_am >= now:
                return dt_am
            if dt_pm >= now:
                return dt_pm
            # both are in the past -> return dt_pm as the later one
            return dt_pm

        # without `now`, default to AM
        return dt_am
    except Exception:
        return None

    # Should be unreachable due to returns above
    return None


def _event_key(date_str: str, event: Dict[str, Any]) -> str:
    name = str(event.get("event_name", "")).strip()
    time = str(event.get("event_time", "")).strip()
    location = str(event.get("event_location", "")).strip()
    raw = f"{date_str}|{name}|{time}|{location}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def send_pushover_notification(title: str, message: str) -> None:
    """
    Send a message through Pushover.

    Env vars expected:
    - PUSHOVER_API_KEY: app token
    - PUSHOVER_USER_KEY: user/device key
    """
    token = os.getenv("PUSHOVER_API_KEY")  # app token
    user = os.getenv("PUSHOVER_USER_KEY")  # user/device key

    if not token or not user:
        raise RuntimeError("Missing PUSHOVER_API_KEY or PUSHOVER_USER_KEY in environment/.env")

    url = "https://api.pushover.net/1/messages.json"
    payload = {
        "token": token,
        "user": user,
        "title": title,
        "message": message,
    }

    r = requests.post(url, data=payload, timeout=30)
    r.raise_for_status()


def run_once(send_ahead_minutes: int = 5, grace_seconds: int = 60) -> None:
    """
    Check events and send reminders.

    The reminder fires when (now - (event_start - send_ahead)) is within grace window.
    """
    calendar = _load_calendar_events()
    reminder_log = _load_reminder_log()

    now = datetime.datetime.now()
    send_delta = datetime.timedelta(minutes=send_ahead_minutes)

    sent_count = 0
    parsed_count = 0
    matched_count = 0

    debug = str(os.getenv("PUSHOVER_DEBUG", "")).lower() in ("1", "true", "yes")

    for date_str, events in calendar.items():
        if not isinstance(events, list):
            continue

        for event in events:
            if not isinstance(event, dict):
                continue

            start_dt = _parse_event_start_datetime(
                date_str,
                event.get("event_time", ""),
                now=now,
            )
            if not start_dt:
                continue
            parsed_count += 1

            reminder_dt = start_dt - send_delta
            diff = (now - reminder_dt).total_seconds()

            # fire within [0, grace_seconds)
            if 0 <= diff < grace_seconds:
                matched_count += 1
                key = _event_key(date_str, event)
                if reminder_log.get(key, {}).get("sent_at"):
                    continue

                title = "Roman Kostenko's Law Office Reminder"
                message = (
                    f"{event.get('event_name', 'Event')} at {event.get('event_time', '')}\n"
                    f"Location: {event.get('event_location', '')}"
                )
                try:
                    if debug:
                        print(
                            f"[DEBUG] Sending reminder: event={event.get('event_name')} "
                            f"start={start_dt.isoformat()} now={now.isoformat()} diff={diff}s"
                        )
                    send_pushover_notification(title=title, message=message)
                except Exception as e:
                    # Don't crash the service; log and continue
                    print(f"[pushover_reminder_service] Failed to send: {e}")
                    continue

                reminder_log[key] = {"sent_at": now.isoformat(), "reminder_for": start_dt.isoformat()}
                sent_count += 1

    _save_reminder_log(reminder_log)
    print(
        f"[pushover_reminder_service] Parsed {parsed_count} event(s), "
        f"matched window {matched_count} time(s), sent {sent_count} reminder(s)."
    )


def run_forever(send_ahead_minutes: int = 5, grace_seconds: int = 60, interval_seconds: int = 60) -> None:
    """
    Keep checking reminders forever.

    For deployments that keep a process alive, you can set PUSHOVER_LOOP=1.
    For most hosted environments, prefer scheduling the script (cron / scheduled jobs)
    instead of keeping a long-running loop.
    """
    while True:
        try:
            run_once(send_ahead_minutes=send_ahead_minutes, grace_seconds=grace_seconds)
        except Exception as e:
            print(f"[pushover_reminder_service] run_forever error: {e}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    ahead_min = int(os.getenv("PUSHOVER_AHEAD_MINUTES", "10"))
    grace_sec = int(os.getenv("PUSHOVER_GRACE_SECONDS", "60"))
    loop = str(os.getenv("PUSHOVER_LOOP", "")).lower() in ("1", "true", "yes")
    if loop:
        interval = int(os.getenv("PUSHOVER_INTERVAL_SECONDS", "60"))
        run_forever(
            send_ahead_minutes=ahead_min,
            grace_seconds=grace_sec,
            interval_seconds=interval,
        )
    else:
        run_once(send_ahead_minutes=ahead_min, grace_seconds=grace_sec)

