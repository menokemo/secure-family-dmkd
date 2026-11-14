"""The Secure Family integration.

مخزن إعداد مركزي للعيلة داخل Home Assistant: الأدمن ينشر الإعداد من التطبيق،
وباقي الأجهزة تقراه فورًا (local push) وتطبّقه عند الدخول. كله محلي على الشبكة،
والكتابة للأدمن بس.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    APP_ID,
    APP_NAME,
    AUTO_CLEANUP_HOURS,
    AUTO_STALE_DAYS,
    DEFAULT_STALE_DAYS,
    DOMAIN,
    DUPLICATE_LAG_HOURS,
    EVENT_LIVE_REQUEST,
    EVENT_UPDATED,
    SERVICE_APPROVE_REGISTRATION,
    SERVICE_CLEANUP_TRACKERS,
    SERVICE_CLEAR,
    SERVICE_DENY_REGISTRATION,
    SERVICE_LIST_PENDING,
    SERVICE_REQUEST_LIVE,
    SERVICE_REQUEST_REGISTRATION,
    SERVICE_ROLLBACK,
    SERVICE_SET_CONFIG,
    SIGNAL_UPDATE,
)
from .device_store import DeviceStore
from .devices import DeviceManager
from .store import ConfigStore

PLATFORMS = ["sensor", "binary_sensor"]

SET_CONFIG_SCHEMA = vol.Schema({vol.Required("config"): dict})
ROLLBACK_SCHEMA = vol.Schema({vol.Optional("version"): int})
CLEAR_SCHEMA = vol.Schema({})
CLEANUP_SCHEMA = vol.Schema(
    {
        vol.Optional("max_age_days", default=DEFAULT_STALE_DAYS): vol.All(
            int, vol.Range(min=1)
        ),
        vol.Optional("dry_run", default=False): bool,
    }
)
REQUEST_LIVE_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.string})
REQUEST_REG_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("webhook_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)
APPROVE_REG_SCHEMA = vol.Schema(
    {vol.Optional("request_id"): cv.string, vol.Optional("code"): cv.string}
)
DENY_REG_SCHEMA = vol.Schema({vol.Required("request_id"): cv.string})
LIST_PENDING_SCHEMA = vol.Schema({})

_LOGGER = logging.getLogger(__name__)


def _is_our_tracker(hass: HomeAssistant, entity_id: str) -> bool:
    """بيتأكد إن الـ entity_id ده device_tracker تابع لتطبيقنا (secure_family)."""
    ent_reg = er.async_get(hass)
    ent = ent_reg.async_get(entity_id)
    if ent is None or ent.config_entry_id is None:
        return False
    cfg = hass.config_entries.async_get_entry(ent.config_entry_id)
    if cfg is None or cfg.domain != "mobile_app":
        return False
    data = cfg.data or {}
    return data.get("app_id") == APP_ID or data.get("app_name") == APP_NAME


async def _clean_stale_trackers(
    hass: HomeAssistant, max_age_days: int, dry_run: bool
) -> dict:
    """ينضّف تسجيلات mobile_app بتاعة تطبيقنا (app_id=secure_family) بس:
    - المكررات: نفس اسم الجهاز → يسيب الأحدث ويشيل الباقي (بقايا إعادة التسجيل).
    - الميتة: ماحدّثتش من أكتر من max_age_days.
    وبيمسح إحصائيات وحالات الكيانات المحذوفة عشان مايفضلش تحذير
    "Entity has no state". عمره ما يلمس تطبيق HA الأصلي (app_id مختلف).
    """
    cutoff = dt_util.utcnow() - timedelta(days=max_age_days)
    ent_reg = er.async_get(hass)
    records: list[dict] = []
    for cfg in list(hass.config_entries.async_entries("mobile_app")):
        data = cfg.data or {}
        if data.get("app_id") != APP_ID and data.get("app_name") != APP_NAME:
            continue
        entities = er.async_entries_for_config_entry(ent_reg, cfg.entry_id)
        trackers = [e.entity_id for e in entities if e.domain == "device_tracker"]
        newest = None
        for tid in trackers:
            state = hass.states.get(tid)
            if state and (newest is None or state.last_updated > newest):
                newest = state.last_updated
        records.append(
            {
                "cfg": cfg,
                "name": data.get("device_name") or cfg.title,
                "newest": newest,
                "entity_ids": [e.entity_id for e in entities],
                "tracker": trackers[0] if trackers else None,
            }
        )

    remove_ids: set[int] = set()
    # المكررات: جمّع بالاسم، سيب الأحدث تحديثًا. مابنشيلش المكرر إلا لو متأخّر
    # عن الأحدث بأكتر من DUPLICATE_LAG_HOURS — عشان لو موبايلين حقيقيين بنفس
    # الاسم (الاتنين بيحدّثوا) مانمسحش ولا واحد منهم.
    by_name: dict[str, list[dict]] = {}
    for rec in records:
        by_name.setdefault(rec["name"], []).append(rec)
    epoch = dt_util.utc_from_timestamp(0)
    lag = timedelta(hours=DUPLICATE_LAG_HOURS)
    for group in by_name.values():
        if len(group) <= 1:
            continue
        keep = max(group, key=lambda r: r["newest"] or epoch)
        if keep["newest"] is None:
            continue
        for rec in group:
            if rec is keep:
                continue
            if rec["newest"] is None or (keep["newest"] - rec["newest"]) > lag:
                remove_ids.add(id(rec))
    # الميتة
    for rec in records:
        if rec["newest"] is not None and rec["newest"] < cutoff:
            remove_ids.add(id(rec))

    items: list[dict] = []
    removed = 0
    purge_ids: list[str] = []
    for rec in records:
        will_remove = id(rec) in remove_ids
        items.append(
            {
                "name": rec["name"],
                "entity_id": rec["tracker"],
                "last_updated": rec["newest"].isoformat() if rec["newest"] else None,
                "remove": will_remove,
            }
        )
        if will_remove and not dry_run:
            purge_ids.extend(rec["entity_ids"])
            await hass.config_entries.async_remove(rec["cfg"].entry_id)
            removed += 1

    if purge_ids:
        try:
            await hass.services.async_call(
                "recorder", "purge_entities", {"entity_id": purge_ids}, blocking=False
            )
        except Exception:  # noqa: BLE001 - recorder مش موجود أو بيرفض، نكمّل
            pass

    to_remove = sum(1 for i in items if i["remove"])
    if dry_run:
        return {"total": len(items), "to_remove": to_remove, "trackers": items}
    if removed:
        _LOGGER.info(
            "Secure Family: cleaned %d stale/duplicate tracker(s): %s",
            removed,
            ", ".join(i["name"] for i in items if i["remove"]),
        )
    hass.bus.async_fire(f"{DOMAIN}_trackers_cleaned", {"removed": removed})
    return {"removed": removed, "total": len(items), "trackers": items}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Secure Family from a config entry."""
    store = ConfigStore(hass)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = store

    # مدير أجهزة التطبيق (جهاز نشط واحد لكل مستخدم + موافقة أدمن) — singleton.
    if "_devices" not in hass.data[DOMAIN]:
        device_store = DeviceStore(hass)
        await device_store.async_load()
        hass.data[DOMAIN]["_devices"] = DeviceManager(hass, device_store)

    async def _user_name(call: ServiceCall) -> str | None:
        """يتأكد إن المنفّذ أدمن ويرجّع اسمه. بيرفض غير الأدمن."""
        user_id = call.context.user_id
        if user_id is None:
            # نداء داخلي موثوق (أتمتة/سكربت على السيرفر).
            return None
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError(
                "Only Home Assistant administrators can change the family configuration."
            )
        return user.name

    def _notify() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE)
        hass.bus.async_fire(EVENT_UPDATED, {"version": store.version})

    async def handle_set(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_set(dict(call.data["config"]), name)
        _notify()

    async def handle_rollback(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_rollback(call.data.get("version"), name)
        _notify()

    async def handle_clear(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_clear(name)
        _notify()

    async def handle_cleanup(call: ServiceCall) -> dict:
        """ينضّف أجهزة تطبيقنا (app_id=secure_family) بس: المكررات + الميتة،
        ويمسح إحصائياتها. dry_run=true بيعرض القايمة من غير مسح. أدمن بس."""
        await _user_name(call)
        return await _clean_stale_trackers(
            hass, call.data["max_age_days"], call.data["dry_run"]
        )

    async def handle_request_live(call: ServiceCall) -> None:
        """يطلق حدث طلب موقع لايف لفرد. متاح لأي فرد مصرّح له (مش أدمن بس).
        بنتأكد إن الـ entity_id تابع لتطبيقنا عشان مايتبعتش لأي كيان عشوائي."""
        entity_id = call.data["entity_id"]
        if not _is_our_tracker(hass, entity_id):
            _LOGGER.warning(
                "request_live_location ignored: %s is not a Secure Family tracker",
                entity_id,
            )
            return
        hass.bus.async_fire(EVENT_LIVE_REQUEST, {"entity_id": entity_id})
        _LOGGER.debug("Secure Family: live location requested for %s", entity_id)

    async def _is_admin_call(call: ServiceCall) -> bool:
        """بيرجّع True لو المنفّذ أدمن (أو نداء داخلي موثوق). بيرفع لو غير أدمن."""
        user_id = call.context.user_id
        if user_id is None:
            return True  # نداء داخلي من السيرفر (أتمتة/سكربت).
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError("Only administrators can do this.")
        return True

    async def handle_request_registration(call: ServiceCall) -> dict:
        """التطبيق يطلب تسجيل جهازه. أي مستخدم مسجّل دخول (مش أدمن بس) —
        بياخد هويته من سياق النداء فمايقدرش يسجّل باسم حد تاني."""
        user_id = call.context.user_id
        if user_id is None:
            raise HomeAssistantError("Must be called by a signed-in user.")
        user = await hass.auth.async_get_user(user_id)
        devices: DeviceManager = hass.data[DOMAIN]["_devices"]
        return await devices.request(
            user_id,
            user.name if user else "User",
            call.data["device_id"],
            call.data["webhook_id"],
            call.data["name"],
        )

    async def handle_approve_registration(call: ServiceCall) -> dict:
        """موافقة: إما request_id من أدمن، أو code من الجهاز الجديد (الكود إثبات
        موافقة الأدمن)."""
        user_id = call.context.user_id
        is_admin = True
        if user_id is not None:
            user = await hass.auth.async_get_user(user_id)
            is_admin = bool(user and user.is_admin)
        devices: DeviceManager = hass.data[DOMAIN]["_devices"]
        return await devices.approve(
            call.data.get("request_id"), call.data.get("code"), is_admin
        )

    async def handle_deny_registration(call: ServiceCall) -> dict:
        await _is_admin_call(call)
        devices: DeviceManager = hass.data[DOMAIN]["_devices"]
        return await devices.deny(call.data["request_id"])

    async def handle_list_pending(call: ServiceCall) -> dict:
        """قائمة الطلبات المعلّقة بالأكواد — للأدمن بس (الكود سرّي)."""
        await _is_admin_call(call)
        devices: DeviceManager = hass.data[DOMAIN]["_devices"]
        return {"pending": devices.list_pending()}

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CONFIG):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_CONFIG, handle_set, schema=SET_CONFIG_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_ROLLBACK, handle_rollback, schema=ROLLBACK_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR, handle_clear, schema=CLEAR_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEANUP_TRACKERS,
            handle_cleanup,
            schema=CLEANUP_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_LIVE, handle_request_live, schema=REQUEST_LIVE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_REQUEST_REGISTRATION,
            handle_request_registration,
            schema=REQUEST_REG_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_APPROVE_REGISTRATION,
            handle_approve_registration,
            schema=APPROVE_REG_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_DENY_REGISTRATION,
            handle_deny_registration,
            schema=DENY_REG_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_LIST_PENDING,
            handle_list_pending,
            schema=LIST_PENDING_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    # تنظيف تلقائي دوري: بيشيل المكررات والأجهزة الميتة بتاعة تطبيقنا ويمسح
    # إحصائياتها — عشان بقايا إعادة التسجيل/إعادة التثبيت ماتتراكمش ولا تطلّع
    # تحذيرات "Entity has no state". بيتسجّل مرة واحدة لكل HA.
    if not hass.data[DOMAIN].get("_auto_cleanup"):
        hass.data[DOMAIN]["_auto_cleanup"] = True

        async def _auto_cleanup(_now) -> None:
            try:
                await _clean_stale_trackers(hass, AUTO_STALE_DAYS, False)
            except Exception:  # noqa: BLE001 - التنظيف الدوري مايوقعش التكامل
                pass

        entry.async_on_unload(
            async_track_time_interval(
                hass, _auto_cleanup, timedelta(hours=AUTO_CLEANUP_HOURS)
            )
        )
        # تنظيفة أولى بعد دقيقتين من الإقلاع (بقايا الجلسة السابقة).
        entry.async_on_unload(async_call_later(hass, 120, _auto_cleanup))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not [
            k for k in hass.data[DOMAIN] if k not in ("_auto_cleanup", "_devices")
        ]:
            hass.data[DOMAIN].pop("_auto_cleanup", None)
            hass.data[DOMAIN].pop("_devices", None)
            for service in (
                SERVICE_SET_CONFIG,
                SERVICE_ROLLBACK,
                SERVICE_CLEAR,
                SERVICE_CLEANUP_TRACKERS,
                SERVICE_REQUEST_LIVE,
                SERVICE_REQUEST_REGISTRATION,
                SERVICE_APPROVE_REGISTRATION,
                SERVICE_DENY_REGISTRATION,
                SERVICE_LIST_PENDING,
            ):
                hass.services.async_remove(DOMAIN, service)
    return unloaded
