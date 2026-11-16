"""توسيع التكرار (recurrence) لتقاويم Secure Family — موديول نقي.

من غير أي استيراد من Home Assistant، عشان نقدر نختبره لوحده بالكامل. بياخد حدث
أساسي (بداية/نهاية + rrule زي "FREQ=YEARLY") ونافذة زمنية، ويرجّع كل النسخ
(occurrences) اللي بتتقاطع مع النافذة — مع الحفاظ على نوع التاريخ (يوم كامل =
date، أو datetime بتوقيت).

بندعم FREQ من: YEARLY · MONTHLY · WEEKLY · DAILY، مع INTERVAL/COUNT/UNTIL.
أي FREQ غير مدعوم بنعامله كحدث مرة واحدة (أأمن من تجاهله).
"""

from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, timedelta, tzinfo

SUPPORTED_FREQ = ("YEARLY", "MONTHLY", "WEEKLY", "DAILY")


def parse_rrule(s: str | None) -> dict:
    """يحوّل نص rrule لمكوّناته. يتجاهل البادئة RRULE: والمفاتيح غير المعروفة."""
    out = {"freq": None, "interval": 1, "count": None, "until": None}
    if not s:
        return out
    for part in str(s).replace("RRULE:", "").split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip().upper()
        v = v.strip()
        if k == "FREQ":
            out["freq"] = v.upper()
        elif k == "INTERVAL":
            try:
                out["interval"] = max(1, int(v))
            except ValueError:
                pass
        elif k == "COUNT":
            try:
                out["count"] = int(v)
            except ValueError:
                pass
        elif k == "UNTIL":
            out["until"] = _parse_until(v)
    return out


def _parse_until(v: str):
    """UNTIL ممكن يكون 20261231 أو 20261231T235959Z. نرجّع date/datetime."""
    v = v.strip().rstrip("Z")
    try:
        if "T" in v:
            return datetime.strptime(v, "%Y%m%dT%H%M%S")
        return datetime.strptime(v, "%Y%m%d").date()
    except ValueError:
        return None


def _replace_ym(d, year: int, month: int):
    """يغيّر السنة/الشهر مع تثبيت اليوم داخل حدود الشهر (29 فبراير → 28)."""
    day = min(d.day, _cal.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def _add_years(d, n: int):
    return _replace_ym(d, d.year + n, d.month)


def _add_months(d, n: int):
    m0 = d.month - 1 + n
    return _replace_ym(d, d.year + m0 // 12, m0 % 12 + 1)


def _shift(start, freq: str, k: int):
    """يرجّع بداية النسخة رقم k (k = index × interval) من البداية الأساسية."""
    if freq == "YEARLY":
        return _add_years(start, k)
    if freq == "MONTHLY":
        return _add_months(start, k)
    if freq == "WEEKLY":
        return start + timedelta(days=7 * k)
    if freq == "DAILY":
        return start + timedelta(days=k)
    return start


def _to_dt(x, tz: tzinfo) -> datetime:
    """يحوّل date/datetime لـ datetime واعي بالمنطقة الزمنية للمقارنة."""
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=tz)
    return datetime(x.year, x.month, x.day, tzinfo=tz)


def to_datetime(x, tz: tzinfo) -> datetime:
    """عام: يحوّل date/datetime لـ datetime واعي (للمقارنة في منصّة التقويم)."""
    return _to_dt(x, tz)


def _overlaps(s, e, win_start, win_end, tz: tzinfo) -> bool:
    return _to_dt(s, tz) < _to_dt(win_end, tz) and _to_dt(e, tz) > _to_dt(win_start, tz)


def _ff_index(start, freq: str, interval: int, win_start, tz: tzinfo) -> int:
    """قفزة تقريبية لأول index قريب من بداية النافذة (ناقص هامش أمان)."""
    sd = start.date() if isinstance(start, datetime) else start
    wd = win_start.date() if isinstance(win_start, datetime) else win_start
    if freq == "YEARLY":
        n = wd.year - sd.year
    elif freq == "MONTHLY":
        n = (wd.year - sd.year) * 12 + (wd.month - sd.month)
    elif freq == "WEEKLY":
        n = (wd - sd).days // 7
    else:  # DAILY
        n = (wd - sd).days
    return max(0, n // interval - 1)


def expand(start, end, rrule, win_start, win_end, tz: tzinfo) -> list[tuple]:
    """كل نسخ الحدث اللي بتتقاطع مع [win_start, win_end]. مرتّبة زمنيًا.

    start/end: date (يوم كامل) أو datetime. النتيجة بنفس النوع.
    """
    p = parse_rrule(rrule)
    freq = p["freq"]
    interval = p["interval"]
    count = p["count"]
    until = p["until"]

    # حدث مرة واحدة (مفيش rrule مدعوم).
    if not rrule or freq not in SUPPORTED_FREQ:
        return [(start, end)] if _overlaps(start, end, win_start, win_end, tz) else []

    if isinstance(start, datetime):
        duration = end - start  # timedelta
    else:
        duration = (end - start).days  # عدد أيام (يوم كامل)

    # UNTIL بتاريخ بدون وقت = شامل اليوم كله (آخره 23:59:59).
    until_dt = None
    if until is not None:
        if isinstance(until, datetime):
            until_dt = _to_dt(until, tz)
        else:
            until_dt = datetime(until.year, until.month, until.day, 23, 59, 59, tzinfo=tz)

    out: list[tuple] = []
    i = _ff_index(start, freq, interval, win_start, tz)
    guard = 0
    while guard < 20000:
        guard += 1
        if count is not None and i >= count:
            break
        occ_start = _shift(start, freq, i * interval)
        if isinstance(occ_start, datetime):
            occ_end = occ_start + duration
        else:
            occ_end = occ_start + timedelta(days=duration)

        # تخطّينا نهاية النافذة؟ خلاص.
        if _to_dt(occ_start, tz) > _to_dt(win_end, tz):
            break
        # UNTIL (على بداية النسخة).
        if until_dt is not None and _to_dt(occ_start, tz) > until_dt:
            break
        if _overlaps(occ_start, occ_end, win_start, win_end, tz):
            out.append((occ_start, occ_end))
        i += 1

    return out
