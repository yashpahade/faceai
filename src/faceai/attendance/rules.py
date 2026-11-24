"""
Attendance rules (pure functions -> aasaani se test).

Window:   [start - open_before_min, end]      bahar => attendance nahi lagti
Status:   start + late_after_min ke baad => "late", warna "present"
Days:     batch ke din (Mon=0..Sun=6) ke alawa => nahi
Duplicate: ek din ek hi record (DB unique constraint + service check)

Saare time LOCAL timezone (settings.timezone, e.g. Asia/Kolkata) mein. Server UTC pe chale to
bhi "9 baje ki class" 9 baje IST hi rahe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass
class Decision:
    allowed: bool
    status: str | None  # present | late
    reason: str


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def decide(
    now_local: datetime,
    start: str,
    end: str,
    days: str,
    late_after_min: int,
    open_before_min: int,
) -> Decision:
    if str(now_local.weekday()) not in days.split(","):
        return Decision(False, None, "no class today")
    day = now_local.date()
    tz = now_local.tzinfo
    start_dt = datetime.combine(day, _t(start), tz)
    end_dt = datetime.combine(day, _t(end), tz)
    opens = start_dt - timedelta(minutes=open_before_min)
    if now_local < opens:
        return Decision(False, None, f"attendance opens at {opens:%H:%M}")
    if now_local > end_dt:
        return Decision(False, None, f"class ended at {end}")
    late = now_local > start_dt + timedelta(minutes=late_after_min)
    return Decision(True, "late" if late else "present", "ok")


def class_over(now_local: datetime, day: date, end: str) -> bool:
    """Us din ki class khatam ho chuki?

    `decide` jaisa hi niyam: end time ke BAAD attendance nahi lagti.

    Purane din hamesha "over". Aaj sirf end time ke baad - tab hi bina record wala student pakka
    absent hai. Class chal rahi ho to absent mat gino (student abhi aa sakta hai).
    """
    today = now_local.date()
    if day != today:
        return day < today
    return now_local > datetime.combine(day, _t(end), now_local.tzinfo)
