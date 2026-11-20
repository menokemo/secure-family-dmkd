"""تكرار المهام — موديول نقي بدون أي استيراد من Home Assistant، عشان نقدر
نختبره لوحده بالكامل.

المهمة المتكرّرة أول ما تتعمل بتتنقل لميعادها الجاي (مش بتتسجّل كخلصانة). هنا
بنحسب الميعاد الجاي من ميعاد حالي + نوع التكرار: يومي (+يوم) · أسبوعي (+٧ أيام) ·
شهري (+شهر مع تثبيت اليوم داخل حدود الشهر). لو الميعاد الناتج لسه فات (المهمة
اتأخّرت كذا دورة)، بنكمّل لقدّام لحد أول ميعاد في المستقبل — عشان مانغرقش الواحد
بدفعة مهام فايتة.
"""

from __future__ import annotations

from datetime import date, timedelta

REPEATS = ("none", "daily", "weekly", "monthly")


def add_months(d: date, n: int) -> date:
    """يضيف n شهر لتاريخ، مع تثبيت اليوم داخل حدود الشهر (31 → 30/28)."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # آخر يوم في الشهر الهدف
    if month == 12:
        last = 31
    else:
        last = (date(year, month + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(d.day, last))


def _step(d: date, repeat: str) -> date | None:
    if repeat == "daily":
        return d + timedelta(days=1)
    if repeat == "weekly":
        return d + timedelta(days=7)
    if repeat == "monthly":
        return add_months(d, 1)
    return None


def next_due(due: date, repeat: str, today: date | None = None) -> date | None:
    """يرجّع الميعاد الجاي بعد `due` حسب `repeat`. لو النتيجة لسه في الماضي
    بالنسبة لـ`today` بيكمّل لقدّام لحد أول ميعاد مستقبلي. بيرجّع None لو مفيش
    تكرار أو نوعه مش معروف.
    """
    if repeat not in REPEATS or repeat == "none":
        return None
    nxt = _step(due, repeat)
    if nxt is None:
        return None
    ref = today or date.today()
    # لو اتأخّرنا كذا دورة، نقفز لأول ميعاد مش فايت (بحد أقصى معقول لتجنّب أي لفة طويلة).
    guard = 0
    while nxt <= ref and guard < 1000:
        step = _step(nxt, repeat)
        if step is None:
            break
        nxt = step
        guard += 1
    return nxt


def parse_date(s: str | None) -> date | None:
    """يحوّل 'YYYY-MM-DD' لتاريخ. أي حاجة غير صحيحة → None."""
    if not s or not isinstance(s, str):
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None
