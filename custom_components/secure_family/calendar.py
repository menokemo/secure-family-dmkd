"""منصّة تقويم Secure Family — ٣ تقاويم مملوكة للمكوّن.

المكوّن بيعمل تقاويمه بنفسه عشان التطبيق (تبويب العائلة) يلاقيها جاهزة بـ
entity_id مضمونة:
  · calendar.secure_family_birthdays   — أعياد الميلاد (تكرار سنوي عادةً)
  · calendar.secure_family_events      — المناسبات
  · calendar.secure_family_appointments — المواعيد

**مفيش تكرار**: كل تقويم له unique_id ثابت، فـHA بيرجّعه نفسه بعد أي إعادة
تشغيل بدل ما يعمل نسخة جديدة، والأحداث متخزّنة في .storage فبتفضل موجودة.
والمنصّة بتتسطّب لأول config entry بس (علامة في hass.data).

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_added_domain
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calendar_recurrence import expand, to_datetime
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CAL_STORAGE_VERSION = 1
CAL_STORAGE_KEY = f"{DOMAIN}_calendars"
_FLAG = "_calendars_entry"  # entry_id اللي عمل التقاويم (عشان مرة واحدة بس)

# التقاويم الثابتة: (key داخلي ثابت، اسم العرض الافتراضي). الاسم محايد بالإنجليزي؛
# التطبيق بيعرض ترجمته. key ثابت → unique_id ثابت → مفيش تكرار.
CALENDARS = (
    ("birthdays", "Secure Family Birthdays"),
    ("events", "Secure Family Events"),
    ("appointments", "Secure Family Appointments"),
    # تقويم خطة الأكل — التطبيق بيخزّن فيه الوجبات (فطار/غدا/عشا) كأحداث، عشان
    # نعيد استخدام بنية التقويم بدل مخزن منفصل. بيتفلتر من عرض الأعمدة في التطبيق.
    ("meals", "Secure Family Meals"),
)


class _CalStore:
    """مخزن مشترك للتقاويم الثلاثة (ملف .storage واحد)."""

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


def _person_key(person_entity_id: str) -> str:
    """مفتاح تقويم فرد ثابت من object_id بتاع كيان person (person.mena → person_mena)."""
    return f"person_{person_entity_id.split('.', 1)[1]}"


def _person_name(hass: HomeAssistant, person_entity_id: str) -> str:
    st = hass.states.get(person_entity_id)
    name = st.attributes.get("friendly_name") if st else None
    return str(name or person_entity_id.split(".", 1)[1])


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """يعمل تقاويم العيلة الثابتة (أعياد ميلاد/مناسبات/مواعيد) + **تقويم لكل فرد**
    (person) تلقائيًا — لأول config entry بس (مفيش تكرار). التقاويم الشخصية
    بتتعمل للموجودين دلوقتي، وأي فرد يتضاف بعدين بياخد تقويمه تلقائيًا من غير
    إعادة تحميل. المفاتيح ثابتة (unique_id) فمفيش تكرار عبر إعادة التشغيل.
    """
    owner = hass.data.setdefault(DOMAIN, {}).get(_FLAG)
    if owner is not None and owner != entry.entry_id:
        return  # تقويم اتعمل من entry تاني — مانعملوش تاني
    hass.data[DOMAIN][_FLAG] = entry.entry_id

    store = _CalStore(hass)
    await store.load()

    created: set[str] = set()

    @callback
    def _add(specs: list[tuple[str, str, str | None]]) -> None:
        """يضيف تقاويم جديدة بس (مش متكررة). spec = (key, name, person_entity_id?)."""
        fresh = [s for s in specs if s[0] not in created]
        for key, _name, _pid in fresh:
            created.add(key)
        if fresh:
            async_add_entities(
                SecureFamilyCalendar(store, key, name, pid) for key, name, pid in fresh
            )

    # الثابتة + تقويم لكل فرد موجود حاليًا.
    specs: list[tuple[str, str, str | None]] = [(k, n, None) for k, n in CALENDARS]
    for pid in hass.states.async_entity_ids("person"):
        specs.append((_person_key(pid), f"{_person_name(hass, pid)} (Secure Family)", pid))
    _add(specs)

    # أي فرد (person) يتضاف بعد كده → تقويمه يتعمل تلقائيًا (بيغطي كمان لو كيانات
    # person اتحمّلت بعد المكوّن، فمفيش مشكلة ترتيب تحميل).
    @callback
    def _person_added(event) -> None:
        eid = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        if not eid or new_state is None:
            return
        _add([(_person_key(eid), f"{new_state.attributes.get('friendly_name') or eid.split('.', 1)[1]} (Secure Family)", eid)])

    entry.async_on_unload(async_track_state_added_domain(hass, ["person"], _person_added))


class SecureFamilyCalendar(CalendarEntity):
    """تقويم محلي مخزّن، بيدعم الإضافة/التعديل/الحذف والتكرار."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(self, store: _CalStore, key: str, name: str, person_entity_id: str | None = None) -> None:
        self._store = store
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{key}"
        # لتقويم فرد: بنعرض كيان الـperson كـattribute عشان التطبيق يربط كل تقويم
        # بصاحبه (عمود لكل فرد) من غير ما يعتمد على اسم/entity_id متغيّر.
        if person_entity_id:
            self._attr_extra_state_attributes = {"person_entity_id": person_entity_id}

    # ===== قراية =====
    @property
    def event(self) -> CalendarEvent | None:
        """أقرب حدث جاي أو شغّال دلوقتي."""
        tz = dt_util.DEFAULT_TIME_ZONE
        now = dt_util.now()
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
        ev = {
            "uid": kwargs.get("uid") or uuid.uuid4().hex,
            "summary": kwargs.get("summary", ""),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "all_day": _is_all_day(start),
            "rrule": kwargs.get("rrule"),
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
                e["start"] = event["dtstart"].isoformat()
                e["all_day"] = _is_all_day(event["dtstart"])
            if "dtend" in event:
                e["end"] = event["dtend"].isoformat()
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
