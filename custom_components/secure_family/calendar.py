"""منصّة تقويم Secure Family — تقاويم عائلية مشتركة مملوكة للمكوّن.

الكل في العيلة بيكتب فيها وبتظهر للكل، وجمب كل حدث بيبان مين أنشأه (التطبيق
بيخزّن المنشئ في الوصف). التقاويم:
  · calendar.secure_family_annual    — مناسبات سنوية (ميلاد/جواز/مناسبات) — كل حدث
      بيتكرر سنويًا تلقائيًا (All-day).
  · calendar.secure_family_planner   — المفكرة: مواعيد وأحداث عابرة بوقت محدّد،
      بتتمسح تلقائيًا أول ما تعدّي.
  · calendar.secure_family_holidays  — الأعياد الرسمية لبلدك (عرض فقط، بتتولّد من
      مكتبة holidays حسب دولة HA).
  · calendar.secure_family_meals     — خطة الأكل (التطبيق بيخزّن فيها الوجبات).

**مفيش تكرار**: كل تقويم له unique_id ثابت، والأحداث متخزّنة في .storage.
**ميجريشن**: التقاويم القديمة (birthdays/events/appointments) وتقاويم الأفراد
(person_*) بتتنقل/بتتشال تلقائيًا مرة واحدة (idempotent).

التكرار (recurrence) بيتحسب في calendar_recurrence.py (موديول نقي متختبر).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calendar_recurrence import expand, to_datetime
from .const import DOMAIN, SIGNAL_UPDATE

_LOGGER = logging.getLogger(__name__)

CAL_STORAGE_VERSION = 1
CAL_STORAGE_KEY = f"{DOMAIN}_calendars"
_FLAG = "_calendars_entry"  # entry_id اللي عمل التقاويم (عشان مرة واحدة بس)
_YEARLY = "FREQ=YEARLY"
_PLANNER_SWEEP = timedelta(hours=6)  # كل كام نظّف المفكرة من اللي عدّى
_BDAY_UID = "sfbday_"  # بادئة أحداث الميلاد المتولّدة تلقائيًا (عشان نعيد توليدها نظيف)

# التقاويم: (key داخلي ثابت، اسم العرض الافتراضي، نوع السلوك). الاسم محايد
# بالإنجليزي؛ التطبيق بيعرض ترجمته. key ثابت → unique_id ثابت → مفيش تكرار.
CALENDARS = (
    ("annual", "Secure Family Annual", "annual"),
    ("planner", "Secure Family Planner", "planner"),
    ("holidays", "Secure Family Holidays", "holidays"),
    ("meals", "Secure Family Meals", "meals"),
)

# ميجريشن: تقويم قديم → (الجديد، يتحوّل سنوي؟)
_MIGRATE = {
    "birthdays": ("annual", True),
    "events": ("annual", True),
    "appointments": ("planner", False),
}


class _CalStore:
    """مخزن مشترك للتقاويم (ملف .storage واحد)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict] = Store(hass, CAL_STORAGE_VERSION, CAL_STORAGE_KEY)
        self.data: dict[str, list[dict]] = {}

    async def load(self) -> None:
        self.data = (await self._store.async_load()) or {}

    async def save(self) -> None:
        await self._store.async_save(self.data)

    def events(self, key: str) -> list[dict]:
        return self.data.setdefault(key, [])

    def set_events(self, key: str, evs: list[dict]) -> None:
        self.data[key] = evs


def _load_dt(value: str, all_day: bool):
    """نص ISO مخزّن → date (يوم كامل) أو datetime واعٍ."""
    if all_day:
        return date.fromisoformat(value)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt


def _is_all_day(x) -> bool:
    return isinstance(x, date) and not isinstance(x, datetime)


def _remove_stale_calendars(hass: HomeAssistant) -> None:
    """يشيل كيانات التقاويم القديمة بتاعة المكوّن من سجل الكيانات: التقاويم
    المشتركة القديمة (birthdays/events/appointments) وكل تقاويم الأفراد
    (person_*). الجديدة (annual/planner/holidays/meals) مابتتمسّش."""
    registry = er.async_get(hass)
    stale = {f"{DOMAIN}_birthdays", f"{DOMAIN}_events", f"{DOMAIN}_appointments"}
    for entity in list(registry.entities.values()):
        if entity.platform != DOMAIN or entity.domain != "calendar":
            continue
        uid = entity.unique_id or ""
        if uid in stale or uid.startswith(f"{DOMAIN}_person_"):
            registry.async_remove(entity.entity_id)


def _migrate_store(data: dict[str, list[dict]]) -> bool:
    """ينقل بيانات التقاويم القديمة للجديد ويشيل تقاويم الأفراد. Idempotent —
    بعد أول مرة التقاويم القديمة بتختفي فمفيش تكرار. بيرجّع True لو اتغيّر حاجة."""
    changed = False
    for old, (new, yearly) in _MIGRATE.items():
        if old not in data:
            continue
        moved = data.pop(old)
        if yearly:
            for e in moved:
                if not e.get("rrule"):
                    e["rrule"] = _YEARLY
        data.setdefault(new, []).extend(moved)
        changed = True
    # تقاويم الأفراد اللي المكوّن كان بيعملها قبل كده — بتتشال.
    for key in [k for k in data if k.startswith("person_")]:
        del data[key]
        changed = True
    return changed


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """يعمل تقاويم العيلة المشتركة الثابتة لأول config entry بس (مفيش تكرار)،
    بيعمل الميجريشن، وبيسجّل تنظيف دوري للمفكرة."""
    owner = hass.data.setdefault(DOMAIN, {}).get(_FLAG)
    if owner is not None and owner != entry.entry_id:
        return  # تقويم اتعمل من entry تاني — مانعملوش تاني
    hass.data[DOMAIN][_FLAG] = entry.entry_id

    # نشيل كيانات التقاويم القديمة من سجل الكيانات (HA مابيشيلهاش لوحده لما
    # نبطّل ننشئها — بتفضل ظاهرة كـ«غير متاحة»).
    _remove_stale_calendars(hass)

    store = _CalStore(hass)
    await store.load()
    if _migrate_store(store.data):
        await store.save()

    entities = {key: SecureFamilyCalendar(store, key, name, kind) for key, name, kind in CALENDARS}
    async_add_entities(entities.values())

    # تنظيف المفكرة: مسح الأحداث اللي عدّت (مش متكررة) — عند الإقلاع وكل ٦ ساعات.
    async def _sweep_planner(_now=None) -> None:
        planner = entities.get("planner")
        if planner is None:
            return
        now = dt_util.now()
        tz = dt_util.DEFAULT_TIME_ZONE
        kept: list[dict] = []
        for e in store.events("planner"):
            if e.get("rrule"):
                kept.append(e)  # متكرر (نادر في المفكرة) — ما يتمسحش
                continue
            try:
                end = _load_dt(e["end"], bool(e.get("all_day")))
            except (KeyError, ValueError):
                kept.append(e)
                continue
            if to_datetime(end, tz) > now:
                kept.append(e)
        if len(kept) != len(store.events("planner")):
            store.set_events("planner", kept)
            await store.save()
            planner.async_write_ha_state()

    await _sweep_planner()
    entry.async_on_unload(async_track_time_interval(hass, _sweep_planner, _PLANNER_SWEEP))

    # توليد أعياد الميلاد تلقائيًا من بروفايلات العيلة (config.profiles) في
    # تقويم المناسبات السنوية — عند الإقلاع وعند أي تغيير في الكونفيج.
    config_store = hass.data.get(DOMAIN, {}).get(entry.entry_id)

    async def _resync_birthdays() -> None:
        config = config_store.config if config_store is not None else {}
        if _sync_birthdays(hass, store, config):
            await store.save()
            annual = entities.get("annual")
            if annual is not None:
                annual.async_write_ha_state()

    await _resync_birthdays()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_UPDATE, lambda: hass.async_create_task(_resync_birthdays()))
    )


def _sync_birthdays(hass: HomeAssistant, store: _CalStore, config: dict) -> bool:
    """يعيد توليد أحداث الميلاد التلقائية في تقويم المناسبات السنوية من
    `config.profiles[person_id].birthday`. الأحداث اليدوية (uid مختلف) بتتساب.
    كل مرة بنمسح المتولّد ونعيد بناءه → idempotent، ويحدّث لو التاريخ اتغيّر.
    بيرجّع True لو الناتج اختلف عن المخزّن (عشان نحفظ بس عند التغيير)."""
    profiles = (config or {}).get("profiles") or {}
    before = store.events("annual")
    manual = [e for e in before if not str(e.get("uid", "")).startswith(_BDAY_UID)]
    auto: list[dict] = []
    for pid, prof in profiles.items():
        if not isinstance(prof, dict):
            continue
        raw = prof.get("birthday")
        if not raw:
            continue
        try:
            d = date.fromisoformat(str(raw))
        except ValueError:
            continue
        name = _person_name(hass, pid)
        auto.append({
            "uid": f"{_BDAY_UID}{pid}",
            "summary": f"🎂 {name}",
            "start": d.isoformat(),
            "end": (d + timedelta(days=1)).isoformat(),
            "all_day": True,
            "rrule": _YEARLY,
            # «خاص بـ» صاحب الميلاد — التطبيق بيعرض صورته جمب الحدث.
            "description": f"·for:{name}",
            "location": None,
        })
    result = manual + auto
    if result == before:
        return False
    store.set_events("annual", result)
    return True


def _holiday_events(hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
    """أعياد رسمية للبلد (من دولة HA) كأحداث يوم-كامل — بتتحسب، مش متخزّنة."""
    country = hass.config.country
    if not country:
        return []
    try:
        import holidays as holidays_lib  # مضمّنة في HA (workday/holiday)

        years = list(range(start_date.year, end_date.year + 1))
        hol = holidays_lib.country_holidays(country.upper(), years=years)
    except Exception:  # noqa: BLE001 — دولة غير مدعومة أو المكتبة غير موجودة
        return []
    lo, hi = start_date.date(), end_date.date()
    out: list[CalendarEvent] = []
    for d, name in hol.items():
        if not isinstance(d, date) or d < lo or d > hi:
            continue
        out.append(
            CalendarEvent(
                start=d,
                end=d + timedelta(days=1),
                summary=str(name),
                uid=f"holiday_{country}_{d.isoformat()}",
            )
        )
    out.sort(key=lambda c: c.start)
    return out


class SecureFamilyCalendar(CalendarEntity):
    """تقويم عائلي مشترك. النوع بيحدّد السلوك:
    annual = كل حدث يتكرر سنويًا (All-day)؛ planner/meals = عادي مخزّن؛
    holidays = عرض فقط ومحسوب من مكتبة holidays."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, store: _CalStore, key: str, name: str, kind: str) -> None:
        self._store = store
        self._key = key
        self._kind = kind
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        self._attr_extra_state_attributes = {"secure_family_kind": kind}
        # الأعياد عرض-فقط؛ الباقي قابل للإضافة/التعديل/الحذف.
        self._attr_supported_features = (
            CalendarEntityFeature(0)
            if kind == "holidays"
            else (
                CalendarEntityFeature.CREATE_EVENT
                | CalendarEntityFeature.DELETE_EVENT
                | CalendarEntityFeature.UPDATE_EVENT
            )
        )

    # ===== قراية =====
    @property
    def event(self) -> CalendarEvent | None:
        """أقرب حدث جاي أو شغّال دلوقتي."""
        tz = dt_util.DEFAULT_TIME_ZONE
        now = dt_util.now()
        if self._kind == "holidays":
            evs = _holiday_events(self.hass, now - timedelta(days=1), now + timedelta(days=400))
            for ev in evs:
                if to_datetime(ev.end, tz) > now:
                    return ev
            return None
        best: tuple[datetime, CalendarEvent] | None = None
        for ev in self._store.events(self._key):
            all_day = bool(ev.get("all_day"))
            try:
                s = _load_dt(ev["start"], all_day)
                e = _load_dt(ev["end"], all_day)
            except (KeyError, ValueError):
                continue
            for occ_s, occ_e in expand(
                s, e, ev.get("rrule"), now - timedelta(days=1), now + timedelta(days=400), tz
            ):
                if to_datetime(occ_e, tz) <= now:
                    continue  # خلص
                start_dt = to_datetime(occ_s, tz)
                if best is None or start_dt < best[0]:
                    best = (start_dt, self._to_event(ev, occ_s, occ_e))
        return best[1] if best else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        if self._kind == "holidays":
            return _holiday_events(hass, start_date, end_date)
        tz = dt_util.DEFAULT_TIME_ZONE
        out: list[CalendarEvent] = []
        for ev in self._store.events(self._key):
            all_day = bool(ev.get("all_day"))
            try:
                s = _load_dt(ev["start"], all_day)
                e = _load_dt(ev["end"], all_day)
            except (KeyError, ValueError):
                continue
            for occ_s, occ_e in expand(s, e, ev.get("rrule"), start_date, end_date, tz):
                out.append(self._to_event(ev, occ_s, occ_e))
        out.sort(key=lambda c: to_datetime(c.start, tz))
        return out

    def _to_event(self, ev: dict, start, end) -> CalendarEvent:
        return CalendarEvent(
            start=start,
            end=end,
            summary=ev.get("summary", ""),
            description=ev.get("description"),
            location=ev.get("location"),
            uid=ev.get("uid"),
            rrule=ev.get("rrule"),
            recurrence_id=(start.isoformat() if ev.get("rrule") else None),
        )

    # ===== كتابة =====
    async def async_create_event(self, **kwargs) -> None:
        start = kwargs["dtstart"]
        end = kwargs["dtend"]
        rrule = kwargs.get("rrule")
        # المناسبات السنوية: كل حدث يوم-كامل ويتكرر سنويًا تلقائيًا.
        if self._kind == "annual":
            if isinstance(start, datetime):
                start = start.date()
            if isinstance(end, datetime):
                end = end.date()
            if not rrule:
                rrule = _YEARLY
        ev = {
            "uid": kwargs.get("uid") or uuid.uuid4().hex,
            "summary": kwargs.get("summary", ""),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "all_day": _is_all_day(start),
            "rrule": rrule,
            "description": kwargs.get("description"),
            "location": kwargs.get("location"),
        }
        self._store.events(self._key).append(ev)
        await self._store.save()
        self.async_write_ha_state()

    async def async_delete_event(
        self, uid: str, recurrence_id: str | None = None, recurrence_range: str | None = None
    ) -> None:
        kept = [e for e in self._store.events(self._key) if e.get("uid") != uid]
        self._store.set_events(self._key, kept)
        await self._store.save()
        self.async_write_ha_state()

    async def async_update_event(
        self,
        uid: str,
        event: dict,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        for e in self._store.events(self._key):
            if e.get("uid") != uid:
                continue
            if "dtstart" in event:
                st = event["dtstart"]
                if self._kind == "annual" and isinstance(st, datetime):
                    st = st.date()
                e["start"] = st.isoformat()
                e["all_day"] = _is_all_day(st)
            if "dtend" in event:
                en = event["dtend"]
                if self._kind == "annual" and isinstance(en, datetime):
                    en = en.date()
                e["end"] = en.isoformat()
            if "summary" in event:
                e["summary"] = event["summary"]
            if "rrule" in event:
                e["rrule"] = event["rrule"]
            if "description" in event:
                e["description"] = event["description"]
            if "location" in event:
                e["location"] = event["location"]
            break
        await self._store.save()
        self.async_write_ha_state()
