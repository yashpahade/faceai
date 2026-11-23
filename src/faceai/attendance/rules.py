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
from datetime import datetime, time, timedelta


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
        return Decision(False, None, "no class today for this batch")
    day = now_local.date()
    tz = now_local.tzinfo
    start_dt = datetime.combine(day, _t(start), tz)
    end_dt = datetime.combine(day, _t(end), tz)
    if now_local < start_dt - timedelta(minutes=open_before_min):
        return Decision(False, None, f"attendance opens at {start} - {open_before_min} min")
    if now_local > end_dt:
        return Decision(False, None, "class is over")
    late = now_local > start_dt + timedelta(minutes=late_after_min)
    return Decision(True, "late" if late else "present", "ok")
